# Teste M1-C: provoca falha de vertex shader no Web. Usado por um Python Controller (modo Module)
# "shader_quebrado.quebrar", ligado a um Sensor Always (pulse off) em um objeto COM material.
# O .py precisa estar na mesma pasta do .range.

VERTEX_QUEBRADO = """
void main() {
    gl_Position = ftransform() +;   // sintaxe invalida de proposito
}
"""

FRAGMENT_OK = """
void main() {
    gl_FragColor = vec4(1.0, 0.0, 1.0, 1.0);
}
"""


def quebrar(cont):
    own = cont.owner
    if not own.meshes or not own.meshes[0].materials:
        print("[shader_quebrado] objeto sem material")
        return
    shader = own.meshes[0].materials[0].getShader()
    if shader is None:
        print("[shader_quebrado] getShader() devolveu None")
        return
    shader.setSource(VERTEX_QUEBRADO, FRAGMENT_OK, True)
    print("[shader_quebrado] setSource chamado; isValid=%s" % shader.isValid())


# Falha de LINK: os dois estagios compilam sozinhos, mas o fragment le um varying que o vertex nao escreve.
VERTEX_OK = """
void main() {
    gl_Position = vec4(0.0, 0.0, 0.0, 1.0);
}
"""

FRAGMENT_SEM_VARYING = """
in vec4 varying_inexistente;
out vec4 cor_saida;
void main() {
    cor_saida = varying_inexistente;
}
"""


def quebrar_link(cont):
    own = cont.owner
    if not own.meshes or not own.meshes[0].materials:
        print("[shader_quebrado] objeto sem material")
        return
    shader = own.meshes[0].materials[0].getShader()
    if shader is None:
        print("[shader_quebrado] getShader() devolveu None")
        return
    shader.setSource(VERTEX_OK, FRAGMENT_SEM_VARYING, True)
    print("[shader_quebrado] link: setSource chamado; isValid=%s" % shader.isValid())
