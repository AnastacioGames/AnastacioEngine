// Amostrador de CPU sem administrador: abre um processo, pausa a thread principal
// a cada ~1 ms, lê a pilha (StackWalk64 + PDB) e soma o tempo por função.
//
//   range_sampler.exe <espera_s> <amostra_s> <saida.txt> <exe> [args...]
//
// Saída: tabela "self" (função no topo da pilha) e "inclusive" (função em
// qualquer ponto da pilha, contada 1x por amostra).
#include <windows.h>
#include <dbghelp.h>
#include <cstdio>
#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <algorithm>

#pragma comment(lib, "dbghelp.lib")
#pragma comment(lib, "winmm.lib")

static std::string Quote(const char *s)
{
	std::string a = s;
	if (a.find(' ') == std::string::npos) return a;
	return "\"" + a + "\"";
}

int main(int argc, char **argv)
{
	if (argc < 5) {
		fprintf(stderr, "uso: range_sampler <espera_s> <amostra_s> <saida.txt> <exe> [args...]\n");
		return 1;
	}
	double wait_s = atof(argv[1]);
	double sample_s = atof(argv[2]);
	const char *out_path = argv[3];
	std::string cmd;
	for (int i = 4; i < argc; i++) {
		if (i > 4) cmd += ' ';
		cmd += Quote(argv[i]);
	}

	STARTUPINFOA si = {sizeof(si)};
	PROCESS_INFORMATION pi = {};
	if (!CreateProcessA(nullptr, &cmd[0], nullptr, nullptr, FALSE, 0, nullptr, nullptr, &si, &pi)) {
		fprintf(stderr, "CreateProcess falhou (%lu)\n", GetLastError());
		return 1;
	}
	timeBeginPeriod(1);
	Sleep((DWORD)(wait_s * 1000));

	// Símbolos só depois da espera: assim os módulos já carregados entram.
	SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES);
	char exe_dir[MAX_PATH];
	strcpy_s(exe_dir, argv[4]);
	char *slash = strrchr(exe_dir, '\\');
	if (!slash) slash = strrchr(exe_dir, '/');
	if (slash) *slash = 0;
	SymInitialize(pi.hProcess, exe_dir, TRUE);

	std::vector<std::vector<DWORD64>> stacks;
	stacks.reserve((size_t)(sample_s * 1100));
	LARGE_INTEGER freq, t0, t;
	QueryPerformanceFrequency(&freq);
	QueryPerformanceCounter(&t0);
	int failed = 0;
	for (;;) {
		QueryPerformanceCounter(&t);
		if ((double)(t.QuadPart - t0.QuadPart) / freq.QuadPart > sample_s) break;
		if (WaitForSingleObject(pi.hProcess, 0) == WAIT_OBJECT_0) break;

		if (SuspendThread(pi.hThread) == (DWORD)-1) { failed++; Sleep(1); continue; }
		CONTEXT ctx = {};
		ctx.ContextFlags = CONTEXT_FULL;
		if (GetThreadContext(pi.hThread, &ctx)) {
			STACKFRAME64 f = {};
			f.AddrPC.Offset = ctx.Rip; f.AddrPC.Mode = AddrModeFlat;
			f.AddrFrame.Offset = ctx.Rbp; f.AddrFrame.Mode = AddrModeFlat;
			f.AddrStack.Offset = ctx.Rsp; f.AddrStack.Mode = AddrModeFlat;
			std::vector<DWORD64> st;
			for (int d = 0; d < 96; d++) {
				if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, pi.hProcess, pi.hThread, &f, &ctx, nullptr,
				                 SymFunctionTableAccess64, SymGetModuleBase64, nullptr))
					break;
				if (f.AddrPC.Offset == 0) break;
				st.push_back(f.AddrPC.Offset);
			}
			stacks.push_back(std::move(st));
		}
		else {
			failed++;
		}
		ResumeThread(pi.hThread);
		Sleep(1);
	}
	timeEndPeriod(1);

	// Resolve endereços -> nome de função (com cache por endereço).
	std::unordered_map<DWORD64, std::string> names;
	auto name_of = [&](DWORD64 a) -> const std::string & {
		auto it = names.find(a);
		if (it != names.end()) return it->second;
		char buf[sizeof(SYMBOL_INFO) + 512];
		SYMBOL_INFO *s = (SYMBOL_INFO *)buf;
		s->SizeOfStruct = sizeof(SYMBOL_INFO);
		s->MaxNameLen = 511;
		DWORD64 disp = 0;
		std::string n;
		if (SymFromAddr(pi.hProcess, a, &disp, s)) {
			n = s->Name;
		}
		else {
			IMAGEHLP_MODULE64 m = {sizeof(m)};
			if (SymGetModuleInfo64(pi.hProcess, a, &m)) n = std::string("[") + m.ModuleName + "]";
			else n = "[?]";
		}
		return names.emplace(a, n).first->second;
	};

	// SAMPLER_FILTER=nome: só conta pilhas que passam por essa função.
	const char *filter = getenv("SAMPLER_FILTER");
	std::unordered_map<std::string, int> self, incl;
	size_t kept = 0;
	for (auto &st : stacks) {
		if (st.empty()) continue;
		if (filter && *filter) {
			bool hit = false;
			for (DWORD64 a : st) {
				if (name_of(a).find(filter) != std::string::npos) { hit = true; break; }
			}
			if (!hit) continue;
		}
		kept++;
		self[name_of(st[0])]++;
		std::unordered_set<std::string> seen;
		for (DWORD64 a : st) {
			const std::string &n = name_of(a);
			if (seen.insert(n).second) incl[n]++;
		}
	}

	TerminateProcess(pi.hProcess, 0);

	FILE *o = fopen(out_path, "w");
	if (!o) o = stdout;
	size_t total = kept ? kept : 1;
	fprintf(o, "amostras %zu (falhas %d) em %.1f s; filtro '%s' -> %zu\n\n", stacks.size(), failed, sample_s,
	        filter ? filter : "", kept);
	auto dump = [&](const char *title, std::unordered_map<std::string, int> &m, int top) {
		std::vector<std::pair<std::string, int>> v(m.begin(), m.end());
		std::sort(v.begin(), v.end(), [](auto &a, auto &b) { return a.second > b.second; });
		fprintf(o, "== %s ==\n", title);
		for (int i = 0; i < (int)v.size() && i < top; i++)
			fprintf(o, "%6.2f%%  %6d  %s\n", 100.0 * v[i].second / total, v[i].second, v[i].first.c_str());
		fprintf(o, "\n");
	};
	dump("self", self, 60);
	dump("inclusive", incl, 120);
	if (o != stdout) fclose(o);
	printf("ok: %zu amostras -> %s\n", total, out_path);
	return 0;
}
