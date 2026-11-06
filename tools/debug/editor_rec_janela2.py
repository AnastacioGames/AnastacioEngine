# Rec Studio: prova do Play embutido em segunda janela. Maximiza a 3D View nas duas janelas: um contexto
# de 3D View passado por script derruba o redesenho de outras areas. REC_RES, REC_LOG; cena criar_cena_rec_exato.py.
import bpy, os, traceback, json
st={'n':0,'fase':0}
R=os.environ['REC_RES']
def rep(t):
    open(R,'a').write(t+'\n')
def ctx(w,scene):
    a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
    r=next(r for r in a.regions if r.type=='WINDOW')
    return {'window':w,'screen':w.screen,'area':a,'region':r,'scene':scene}
def run(scene):
    st['n']+=1
    wm=bpy.context.window_manager
    try:
        if st['fase']==0 and st['n']>=3:
            st['fase']=1; st['n']=0
            rep('dup: %s' % bpy.ops.wm.window_duplicate(ctx(wm.windows[0],scene)))
            rep('janelas: %d' % len(wm.windows))
        elif st['fase']==1 and st['n']>=5:
            st['fase']=10; st['n']=0
            for w in list(wm.windows):
                bpy.ops.screen.screen_full_area(ctx(w,scene))
            rep('maximizadas')
        elif st['fase']==10 and st['n']>=5:
            st['fase']=2
            bpy.app.handlers.scene_update_post.remove(run)
            w=wm.windows[-1]
            rep('telas: %s' % [x.screen.name for x in wm.windows])
            scene.ae_rec_countdown=0; scene.ae_rec_max_duration=2.0; scene.ae_rec_make_keyframes=False
            os.environ['REC_MOVER']='1'
            rep('rec janela2: %s' % bpy.ops.view3d.game_record(ctx(w,scene)))
            rep('passos %d' % len(json.load(open(os.environ['REC_LOG']))))
            os.environ['REC_MOVER']='0'
            rep('watch janela2: %s' % bpy.ops.view3d.game_record(ctx(w,scene),watch=True))
            rep('passos %d; janelas %d; takes %d' % (len(json.load(open(os.environ['REC_LOG']))),len(wm.windows),len(scene.ae_rec_takes)))
            rep('FIM'); os._exit(0)
    except Exception:
        rep('ERRO\n'+traceback.format_exc()); os._exit(1)
bpy.app.handlers.scene_update_post.append(run)
