// Monta "/saves" como IDBFS e traz o conteudo do IndexedDB para o MEMFS
// ANTES de main() rodar, para que loadGamePythonConfig() (fopen sincrono em
// KX_PythonInit.cpp) já encontre os arquivos de save da sessão anterior.
// Sem isso, todo save feito via bge.logic.saveGlobalDict() ficaria só na
// memória do processo e desapareceria ao fechar a aba. Ver
// pathGamePythonConfig() em KX_PythonInit.cpp (redireciona saves para
// "/saves" só sob __EMSCRIPTEN__) e o EM_ASM de FS.syncfs(false, ...) logo
// após a escrita do save, que manda a mudança de volta para o IndexedDB.
Module["preRun"] = (Module["preRun"] || []).concat([function () {
	// Exposto para o smoke test de persistencia (tools/web/verify-persistence.cjs).
	Module["FS"] = FS;
	FS.mkdir("/saves");
	FS.mount(IDBFS, {}, "/saves");

	Module.addRunDependency("idbfs-initial-sync");
	FS.syncfs(true, function (err) {
		if (err) {
			console.error("[web-save] syncfs (initial read) failed:", err);
		}
		Module.removeRunDependency("idbfs-initial-sync");
	});
}]);
