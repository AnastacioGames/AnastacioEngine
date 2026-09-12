use std::io::{BufRead, BufReader};
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver};
use std::sync::{Arc, Mutex};
use std::thread;

enum RunnerEvent {
    Line(String),
    Exited,
}

/// A `release/scripts/*.py` task running in the background: two reader
/// threads stream its stdout/stderr into a channel, and a third thread just
/// waits on the child so we know when it's gone. `poll()` drains that
/// channel from the UI thread once per frame — this is the replacement for
/// `editor.gd::_run_script`'s blocking `OS.execute(..., blocking=true)`,
/// which froze the whole UI for the duration of every build/export.
pub struct RunningTask {
    pub label: String,
    pub log: Vec<String>,
    /// Count of `build_data.py`'s per-file/per-chunk progress lines.
    pub progress: usize,
    /// Latest `build_release.py` `STAGE n/4` banner, if any.
    pub stage: Option<String>,
    /// `None` while running; `Some(success)` once the process has exited.
    pub finished: Option<bool>,
    has_error: bool,
    receiver: Receiver<RunnerEvent>,
    child: Arc<Mutex<Option<Child>>>,
}

impl RunningTask {
    pub fn spawn(
        label: impl Into<String>,
        python: &Path,
        script: &Path,
        project_config: &Path,
        extra_args: &[String],
    ) -> std::io::Result<Self> {
        let mut command = Command::new(python);
        // `-u`: Python fully buffers stdout/stderr instead of line-buffering
        // whenever they're redirected to a pipe (as opposed to a terminal).
        // Without this, none of the live streaming below would show
        // anything until the buffer filled or the process exited — the
        // exact "frozen, then dumps everything at once" symptom this whole
        // module exists to avoid.
        command.arg("-u").arg(script).arg("--project").arg(project_config);
        for arg in extra_args {
            command.arg(arg);
        }
        command.stdout(Stdio::piped()).stderr(Stdio::piped());

        let mut child = command.spawn()?;
        let stdout = child.stdout.take().expect("stdout is piped above");
        let stderr = child.stderr.take().expect("stderr is piped above");

        let (tx, rx) = mpsc::channel();
        let child = Arc::new(Mutex::new(Some(child)));

        let tx_out = tx.clone();
        thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if tx_out.send(RunnerEvent::Line(line)).is_err() {
                    return;
                }
            }
        });

        let tx_err = tx.clone();
        thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                if tx_err.send(RunnerEvent::Line(line)).is_err() {
                    return;
                }
            }
        });

        let child_wait = Arc::clone(&child);
        thread::spawn(move || {
            if let Some(mut c) = child_wait.lock().unwrap().take() {
                let _ = c.wait();
            }
            let _ = tx.send(RunnerEvent::Exited);
        });

        Ok(Self {
            label: label.into(),
            log: Vec::new(),
            progress: 0,
            stage: None,
            finished: None,
            has_error: false,
            receiver: rx,
            child,
        })
    }

    /// Drains everything the background threads have produced since the
    /// last call. Call once per frame while a task is active.
    pub fn poll(&mut self) {
        while let Ok(event) = self.receiver.try_recv() {
            match event {
                RunnerEvent::Line(line) => {
                    // None of these scripts ever exit non-zero (every one
                    // wraps `main()` in `try/except: print(e)`), so an "X "
                    // prefix in the printed output is the only real failure
                    // signal — see the RangeArmor release scripts research.
                    if line.trim_start().starts_with("X ") {
                        self.has_error = true;
                    }
                    if line.starts_with("> Writing") || line.starts_with("> Written chunk") {
                        self.progress += 1;
                    }
                    if line.starts_with("STAGE") {
                        self.stage = Some(line.clone());
                    }
                    self.log.push(line);
                }
                RunnerEvent::Exited => {
                    self.finished = Some(!self.has_error);
                }
            }
        }
    }

    /// Kills the child process directly. Note this does not kill any
    /// grandchild processes the script itself may have spawned (Rust's
    /// `Child::kill` has no notion of a process tree) — a known limitation,
    /// not a full job-object-based tree kill.
    pub fn cancel(&mut self) {
        if let Some(mut child) = self.child.lock().unwrap().take() {
            let _ = child.kill();
        }
        self.log.push("--- cancelled ---".to_owned());
        self.finished = Some(false);
    }

    pub fn is_running(&self) -> bool {
        self.finished.is_none()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{Duration, Instant};

    /// Polls `task` until it reports finished, or panics after `timeout` —
    /// stands in for the per-frame `poll()` calls the real UI loop makes.
    fn wait_until_finished(task: &mut RunningTask, timeout: Duration) {
        let start = Instant::now();
        while task.finished.is_none() {
            task.poll();
            assert!(start.elapsed() < timeout, "task did not finish within {timeout:?}");
            thread::sleep(Duration::from_millis(10));
        }
    }

    /// Writes a throwaway `.py` file so tests exercise a *real* Python
    /// process end-to-end (this machine has a working `python` on PATH),
    /// rather than mocking the process boundary the whole module exists to
    /// manage asynchronously.
    fn write_script(name: &str, body: &str) -> std::path::PathBuf {
        let path = std::env::temp_dir().join(format!(
            "rangearmor_runner_test_{name}_{}_{}.py",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::write(&path, body).unwrap();
        path
    }

    #[test]
    fn streams_stdout_lines_live_and_reports_success() {
        let script = write_script(
            "success",
            "import sys\nprint('> Writing a.txt')\nprint('> Writing b.txt')\nprint('done')\n",
        );
        let mut task = RunningTask::spawn(
            "Test task",
            Path::new("python"),
            &script,
            Path::new("unused-project-config.json"),
            &[],
        )
        .expect("python must be on PATH for this test");

        wait_until_finished(&mut task, Duration::from_secs(10));

        assert_eq!(task.finished, Some(true));
        assert_eq!(task.progress, 2, "both '> Writing' lines should count as progress");
        assert!(task.log.iter().any(|l| l == "done"));

        let _ = std::fs::remove_file(&script);
    }

    #[test]
    fn an_x_prefixed_line_marks_the_task_as_failed_despite_exit_code_zero() {
        // Mirrors every `release/scripts/*.py`: they catch their own
        // exceptions and print "X ...", but the process itself still exits
        // 0 — so success must come from scanning output, not the exit code.
        let script = write_script("failure", "print('X something broke')\n");
        let mut task = RunningTask::spawn(
            "Test task",
            Path::new("python"),
            &script,
            Path::new("unused-project-config.json"),
            &[],
        )
        .unwrap();

        wait_until_finished(&mut task, Duration::from_secs(10));

        assert_eq!(task.finished, Some(false));

        let _ = std::fs::remove_file(&script);
    }

    #[test]
    fn cancel_kills_the_process_and_marks_it_not_successful() {
        let script = write_script(
            "long_running",
            "import time\nprint('starting')\ntime.sleep(30)\nprint('should never print')\n",
        );
        let mut task = RunningTask::spawn(
            "Test task",
            Path::new("python"),
            &script,
            Path::new("unused-project-config.json"),
            &[],
        )
        .unwrap();

        // Give it a moment to actually start and print its first line
        // before cancelling, so this exercises a genuine in-flight kill.
        let start = Instant::now();
        while task.log.is_empty() && start.elapsed() < Duration::from_secs(5) {
            task.poll();
            thread::sleep(Duration::from_millis(10));
        }
        assert!(!task.log.is_empty(), "process should have printed its first line by now");

        task.cancel();
        assert_eq!(task.finished, Some(false));
        assert!(!task.is_running());
        assert!(!task.log.iter().any(|l| l == "should never print"));

        let _ = std::fs::remove_file(&script);
    }
}
