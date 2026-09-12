Demo ImGui
==========

Abra ImGui_example.range para consultar o projeto completo.

Para usar o menu principal em outro projeto, copie a pasta `scripts` inteira
para a mesma pasta do seu arquivo .range. No componente Python, informe:

    Modulo: scripts.imgui_main_menu_component
    Classe: MainMenuComponent

Ou, caso o editor mostre os dois no mesmo campo:

    scripts.imgui_main_menu_component.MainMenuComponent

Nao copie apenas imgui_main_menu_component.py: ele depende de
scripts/menu_common.py, que agora acompanha o demo.
