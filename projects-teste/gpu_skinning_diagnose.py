"""
Diagnostico de GPU Skinning - rodar no Text Editor do Range Engine (Blender 2.79)
com o personagem problematico selecionado (mesh + armature, ou so a mesh
com o modifier Armature apontando pro armature certo).

Uso: seleciona o objeto MESH do personagem (ativo) e roda o script.
Ele acha o armature automaticamente pelo modifier Armature.

Reporta:
  1) grupos de vertice sem bone correspondente (nome nao bate ou bone com deform desligado)
  2) bones deform=True sem grupo de vertice correspondente (silencioso, so informativo)
  3) numero de bones deformantes vs limite de 64 (GPU_MAX_SKINNING_BONES)
  4) vertices com mais de 4 pesos != 0 (GPU so usa os 4 maiores, perde os outros)
  5) se o armature esta em modo 'RanGE GPU Skinning' (deform_method == BGE_GPU)
  6) se algum material do mesh tem "GPU Skinning" habilitado (use_gpu_skinning)
"""
import bpy

MAX_GPU_BONES = 64

obj = bpy.context.active_object
if obj is None or obj.type != 'MESH':
    print("ERRO: selecione o objeto MESH do personagem como ativo antes de rodar.")
else:
    me = obj.data

    arma_obj = None
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            arma_obj = mod.object
            break

    if arma_obj is None:
        print("ERRO: nenhum modifier Armature com objeto atribuido encontrado em '%s'." % obj.name)
    else:
        print("=" * 70)
        print("Mesh: %s   Armature: %s" % (obj.name, arma_obj.name))
        print("=" * 70)

        # --- 5) modo de deform do armature ---
        deform_method = arma_obj.data.deform_method
        print("\n[5] Armature.deform_method = %s" % deform_method)
        if deform_method != 'BGE_GPU':
            print("    -> NAO esta em 'RanGE GPU Skinning'. Isso sozinho ja faz cair pro CPU")
            print("       (nao explica distorcao, mas confirma se o GPU path esta ativo).")

        # --- 6) materiais com GPU Skinning habilitado ---
        print("\n[6] Materiais do mesh:")
        any_gpu_mat = False
        for slot in obj.material_slots:
            if slot.material is None:
                continue
            flag = getattr(slot.material, "use_gpu_skinning", False)
            print("    - %-30s use_gpu_skinning = %s" % (slot.material.name, flag))
            any_gpu_mat = any_gpu_mat or flag
        if not any_gpu_mat:
            print("    -> NENHUM material com GPU Skinning habilitado. Vai cair pro CPU skinning.")

        # --- bones deformantes e nomes ---
        deform_bones = {b.name for b in arma_obj.data.bones if b.use_deform}
        all_bone_names = {b.name for b in arma_obj.data.bones}

        vgroup_names = [vg.name for vg in obj.vertex_groups]

        # --- 3) contagem vs limite ---
        print("\n[3] Grupos de vertice no mesh: %d   Limite GPU: %d" % (len(vgroup_names), MAX_GPU_BONES))
        if len(vgroup_names) > MAX_GPU_BONES:
            print("    -> EXCEDE o limite. O engine ja detecta isso e cai pro CPU sozinho")
            print("       (nao deveria causar distorcao, so perda de performance).")

        # --- 1) grupos sem bone correspondente valido ---
        print("\n[1] Grupos de vertice SEM bone deformante correspondente (index shift / vertice preso no bind pose):")
        found_bad = False
        for name in vgroup_names:
            if name not in all_bone_names:
                print("    - grupo '%s': NENHUM bone com esse nome no armature (nome digitado errado / bone renomeado)" % name)
                found_bad = True
            elif name not in deform_bones:
                print("    - grupo '%s': bone existe mas esta com 'Deform' DESLIGADO (Bone Properties > Deform)" % name)
                found_bad = True
        if not found_bad:
            print("    (nenhum problema encontrado)")

        # --- 2) bones deformantes sem grupo (so informativo) ---
        print("\n[2] Bones deformantes SEM grupo de vertice (nao influenciam nada, so informativo):")
        missing_groups = sorted(deform_bones - set(vgroup_names))
        if missing_groups:
            for n in missing_groups:
                print("    - %s" % n)
        else:
            print("    (nenhum)")

        # --- 4) mais de 4 pesos por vertice ---
        print("\n[4] Vertices com mais de 4 grupos de peso != 0 (GPU trunca pros 4 maiores, resto e' ignorado):")
        max_influences = 0
        over4_count = 0
        worst_vertex = -1
        for v in me.vertices:
            nonzero = [g for g in v.groups if g.weight > 0.0]
            n = len(nonzero)
            if n > max_influences:
                max_influences = n
                worst_vertex = v.index
            if n > 4:
                over4_count += 1
        print("    Maior numero de influencias em um unico vertice: %d (vertice index %d)" % (max_influences, worst_vertex))
        print("    Vertices com mais de 4 influencias: %d de %d" % (over4_count, len(me.vertices)))
        if over4_count > 0:
            print("    -> pode causar diferenca visual sutil vs. modo Blender, mas normalmente")
            print("       nao causa a distorcao tipo 'sentado' (isso e' mais tipico de grupo sem bone).")

        print("\n" + "=" * 70)
        print("Resumo: se [1] encontrou algo, e' o suspeito principal.")
        print("Se [1] e [2] vierem limpos e [5]/[6] estiverem OK, comparar visualmente")
        print("a ordem/nome dos vertex groups deste mesh com o do personagem que funciona.")
        print("=" * 70)
