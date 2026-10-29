# SPDX-License-Identifier: GPL-2.0-or-later
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details. You should have received a copy of the GNU General
# Public License along with this program; if not, see <https://www.gnu.org/licenses/>.

"""Reference for the legacy Principled shader (numpy only).

Generate with D-distributed Hammersley samples; validate with independent
log(tan(theta_h)) quadrature and midpoint azimuth, including its convergence.
Inputs are post specular-AA roughness. No diffuse or coat 0.25 weight here.
"""
import argparse
import json
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
CONVERGENCE_RELATIVE_TOLERANCE = .001
CONVERGENCE_ABSOLUTE_TOLERANCE = 1e-8


def smith(c, a):
    return 1.0 / (c + np.sqrt(a*a + (1-a*a)*c*c))


def fresnel(c, eta):
    # Shader fresnel_dielectric_cos for positive cosines and eta >= 1.
    g = np.sqrt(np.maximum(eta*eta - 1 + c*c, 0))
    with np.errstate(divide='ignore', invalid='ignore'):
        f = 0.5*((g-c)/(g+c))**2 * (1+((c*(g+c)-1)/(c*(g-c)+1))**2)
    return np.nan_to_num(f)


def radical_inverse(n):
    bits = np.arange(n, dtype=np.uint32)
    bits = (bits << 16) | (bits >> 16)
    bits = ((bits & 0x55555555) << 1) | ((bits & 0xAAAAAAAA) >> 1)
    bits = ((bits & 0x33333333) << 2) | ((bits & 0xCCCCCCCC) >> 2)
    bits = ((bits & 0x0F0F0F0F) << 4) | ((bits & 0xF0F0F0F0) >> 4)
    bits = ((bits & 0x00FF00FF) << 8) | ((bits & 0xFF00FF00) >> 8)
    return (bits.astype(float)+0.5) / 2**32


def integrate(nv, rough, count=65536):
    """Importance sampled D(H)*NoH; return A, B, Ecc, Ess_lit."""
    u = (np.arange(count)+0.5)/count
    cp = np.cos(2*np.pi*radical_inverse(count))
    results = []
    for coat in (False, True):
        a = max(rough*rough, .001) if coat else max(rough, .1)**2
        ch2 = (1-np.power(a*a, 1-u))/(1-a*a) if coat and a < 1 else (
            1-u if coat else (1-u)/(1+(a*a-1)*u))
        ch = np.sqrt(ch2)
        vh = np.sqrt(1-nv*nv)*np.sqrt(1-ch2)*cp + nv*ch
        nl = 2*vh*ch-nv
        mask = (nl > 0) & (vh > 0)
        nl = np.maximum(nl, 0)
        g = .25 if coat else a
        w = np.where(mask, 4*vh*nl*smith(nv, g)*smith(nl, g)/ch, 0)
        if coat:
            results.append(np.mean(w*fresnel(np.maximum(vh, 0), 1.5)))
        else:
            fc = np.maximum(1-vh, 0)**5
            results.extend([np.mean(w*(1-fc)), np.mean(w*fc)])
            g = (.5*rough+.5)**2
            lit = np.mean(np.where(mask, 4*vh*nl*smith(nv, g)*smith(nl, g)/ch, 0))
    return np.array([results[0], results[1], results[2], lit])


def quadrature(nv, rough, level, etas):
    """Independent H-space integration, not inverse-D sampling.

    Log-tan grid resolves narrow cores and tails. dOmega_H = sin²H cosH dt dphi;
    dOmega_L = 4 VdotH dOmega_H (the inverse is for the sampling PDF).
    """
    order = 8
    x, weights = np.polynomial.legendre.leggauss(order)
    edges = np.linspace(-18, 14, 32*2**level+1)
    t = ((edges[:-1,None]+edges[1:,None])/2 + np.diff(edges)[:,None]*x/2).ravel()
    wt = (np.diff(edges)[:,None]*weights/2).ravel()
    tan = np.exp(t)
    ch = (1+tan*tan)**-.5
    sh = tan*ch
    nphi = 128*2**level
    cp = np.cos(2*np.pi*(np.arange(nphi)+.5)/nphi)
    vh = np.sqrt(1-nv*nv)*sh[:,None]*cp + nv*ch[:,None]
    nl = np.maximum(2*vh*ch[:,None]-nv, 0)
    jac = np.maximum(4*vh, 0)*sh[:,None]**2*ch[:,None]*wt[:,None]*(2*np.pi/nphi)
    a = max(rough,.1)**2
    # Stable D formula, avoiding cancellation near H=N.
    d = a*a/(np.pi*(sh*sh+a*a*ch*ch)**2)
    w = d[:,None]*smith(nv,a)*smith(nl,a)*nl*jac
    fc = np.maximum(1-vh,0)**5
    ab = [np.sum(w*(1-fc)), np.sum(w*fc)]
    exact = []
    for eta in etas:
        f0 = ((eta-1)/(eta+1))**2
        fh = (fresnel(np.maximum(vh,0),eta)-f0)/(1-f0)
        exact.append([np.sum(w*(1-fh)), np.sum(w*fh)])
    g = (.5*rough+.5)**2
    lit = np.sum(d[:,None]*smith(nv,g)*smith(nl,g)*nl*jac)
    a = max(rough*rough,.001)
    d = np.full_like(ch,1/np.pi) if a >= 1 else (a*a-1)/(np.pi*np.log(a*a)*(sh*sh+a*a*ch*ch))
    cc = np.sum(d[:,None]*smith(nv,.25)*smith(nl,.25)*nl*jac*fresnel(np.maximum(vh,0),1.5))
    return np.array(ab+[cc,lit]), np.array(exact)


def reference(nv, rough, etas):
    previous = None
    for level in range(5):
        value, exact = quadrature(nv,rough,level,etas)
        joined = np.r_[value,exact.ravel()]
        if previous is not None:
            # Each channel: delta < max(0.1% * abs(value), 1e-8).
            delta = np.abs(joined-previous)
            tolerance = np.maximum(CONVERGENCE_RELATIVE_TOLERANCE*np.abs(joined),
                                   CONVERGENCE_ABSOLUTE_TOLERANCE)
            normalized_delta = float(np.max(delta/tolerance))
            if normalized_delta < 1:
                return value,exact,{'level':level,'samples':(256*2**level)*(128*2**level),
                                    'max_relative_delta':normalized_delta*CONVERGENCE_RELATIVE_TOLERANCE,
                                    'max_normalized_delta':normalized_delta,
                                    'max_absolute_delta':float(delta.max())}
        previous = joined
    raise RuntimeError('Quadrature did not converge at nv=%g r=%g' % (nv,rough))


def sample(lut,nv,r):
    n = len(lut)
    px,py = np.clip(np.array([nv,r])*n-.5,0,n-1)
    x,y = int(px),int(py)
    fx,fy = px-x,py-y
    return ((1-fy)*((1-fx)*lut[y,x]+fx*lut[y,min(x+1,n-1)]) +
            fy*((1-fx)*lut[min(y+1,n-1),x]+fx*lut[min(y+1,n-1),min(x+1,n-1)]))


def karis(nv,r):
    rr = r*np.array([-1,-.0275,-.572,.022])+[1,.0425,1.04,-.04]
    a004 = min(rr[0]**2,2**(-9.28*nv))*rr[0]+rr[1]
    return np.array([-1.04,1.04])*a004+rr[2:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=REPO_ROOT/'artifacts/bsdf-energia',
                        help='Output directory; relative paths are resolved against the repository')
    parser.add_argument('--samples',type=int,default=131072)
    parser.add_argument('--reuse-luts',action='store_true',help='Revalidate saved .npy tables without regenerating them')
    parser.add_argument('--probe-sqrt',action='store_true',help='Test a proposed sqrt(NoV) coordinate using only required texels; does not emit a header')
    parser.add_argument('--probe-endpoints',action='store_true',help='Probe sqrt(NoV) with endpoint-inclusive grids; proposed contract only, no header')
    parser.add_argument('--probe-size',type=int,help='Probe a larger uniform table using only required texels; does not emit a header')
    args = parser.parse_args()
    if not args.out.is_absolute():
        args.out = REPO_ROOT/args.out
    args.out.mkdir(parents=True,exist_ok=True)
    specs = [0,.01,.25,.5,1]
    etas = [2/(1-np.sqrt(.08*s))-1 for s in specs]
    points = [(v,r) for v in (.01,.05,.173,.527,.931,1.) for r in (0.,.1,.237,.673,1.)]
    refs = []
    for nv,r in points:
        value,exact,conv = reference(nv,r,etas)
        refs.append({'nv':nv,'roughness':r,'value':value.tolist(),
                     'exact_ab':exact.tolist(),'convergence':conv})
    report = {'etas':etas,'specular':specs,'references':refs,'samples_per_texel':args.samples,'contract':'v3.2: RGBA=A,B,Ecc,0; shared ms from Ess_env','resolutions':[]}
    report['convergence_tolerance'] = {'relative':CONVERGENCE_RELATIVE_TOLERANCE,
                                       'absolute':CONVERGENCE_ABSOLUTE_TOLERANCE}
    # Exact analytic white-Fresnel case: at NoV=1,a=g=1, integral=1-log(2).
    analytic = next(ref for ref in refs if ref['nv'] == 1 and ref['roughness'] == 1)
    analytic_error = abs(sum(analytic['value'][:2])-(1-np.log(2)))
    assert analytic_error < 1e-6, analytic_error
    report['analytic_rough_normal_error'] = float(analytic_error)
    if args.probe_sqrt or args.probe_endpoints or args.probe_size:
        n = args.probe_size or 64
        lut = np.full((n,n,4),np.nan)
        cache = set()
        cases = []
        for ref in refs:
            nv,r = ref['nv'],ref['roughness']
            uv,rv = (nv if args.probe_size else np.sqrt(nv)),r
            if args.probe_endpoints:
                uv,rv = (np.array([uv,rv])*(n-1)+.5)/n
            x,y = np.clip(np.array([uv,rv])*n-.5,0,n-1).astype(int)
            for iy in (y,min(y+1,n-1)):
                for ix in (x,min(x+1,n-1)):
                    if (iy,ix) not in cache:
                        physical_nv,physical_r = (ix+.5)/n,(iy+.5)/n
                        if not args.probe_size:
                            physical_nv = physical_nv**2
                        if args.probe_endpoints:
                            physical_nv,physical_r = (ix/(n-1))**2,iy/(n-1)
                        lut[iy,ix] = integrate(physical_nv,physical_r,args.samples).astype(np.float16).astype(float)
                        cache.add((iy,ix))
            val = np.array(ref['value'])
            got = sample(lut,uv,rv)
            furnace = [sum(val[:2])/sum(got[:2]),val[3]*max(1,1/got[3])]
            cases.append({'nv':nv,'roughness':r,'error':(got-val).tolist(),'furnace':furnace})
        report = {'proposal':('%dx%d uniform cell centers'%(n,n) if args.probe_size else
                             '64x64 endpoint grid; texel NoV=(x/63)^2, roughness=y/63' if args.probe_endpoints else
                             '64x64, U=sqrt(NoV); texel NoV=U^2; V=roughness'),
                  'partial_table_only':True,'evaluated_texels':len(cache),'cases':cases,
                  'max_abs_channel_error':np.max(np.abs([c['error'] for c in cases]),axis=0).tolist(),
                  'max_abs_furnace_error':np.max(np.abs(np.array([c['furnace'] for c in cases])-1),axis=0).tolist()}
        name = 'probe_endpoints64.json' if args.probe_endpoints else 'probe_sqrt64.json'
        if args.probe_size:
            name = 'probe_uniform%d.json'%n
        (args.out/name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k != 'cases'},indent=2))
        return
    for n in (32,64):
        print('Generating %dx%d' % (n,n),flush=True)
        if args.reuse_luts:
            lut = np.load(args.out/('lut_%d.npy'%n))
            assert lut.shape == (n,n,4)
        else:
            lut = np.empty((n,n,4))
            for y in range(n):
                for x in range(n):
                    lut[y,x] = integrate((x+.5)/n,(y+.5)/n,args.samples)
                if y % 8 == 7:
                    print('  row %d/%d' % (y+1,n),flush=True)
        # Include half-float storage rounding in GPU-equivalent interpolation.
        lut = lut.astype(np.float16).astype(float)
        cases=[]
        for ref in refs:
            nv,r = ref['nv'],ref['roughness']
            val = np.array(ref['value'])
            got = sample(lut,nv,r)
            err = got-val
            extreme = nv <= .05 or r in (0.,.1,1.)
            furnace = (val[[0,1]].sum()/got[[0,1]].sum(),val[3]*max(1,1/got[3]))
            cases.append({'nv':nv,'roughness':r,'lut':got.tolist(),'error':err.tolist(),
                          'ess_error':float(err[0]+err[1]),'furnace':list(furnace),
                          'lit_furnace_diagnostic_only':True,
                          'pass':bool(abs(err[0]+err[1]) <= (.03 if extreme else .01)
                                      and abs(err[2]) <= (.03 if extreme else .01)
                                      and abs(furnace[0]-1) <= .03)})
        passed = all(c['pass'] for c in cases)
        report['resolutions'].append({'size':n,'pass':passed,'cases':cases,
             'min_ess_lit':float(lut[:,:,3].min()),'max_ess_lit':float(lut[:,:,3].max()),
             'max_abs_lit_minus_env':float(np.max(np.abs(lut[:,:,3]-lut[:,:,:2].sum(axis=2))))})
        np.save(args.out/('lut_%d.npy'%n),lut)
        if passed:
            break
    report['selected_size'] = n if passed else None
    report['fresnel_max_abs_ab_error'] = [float(max(np.max(np.abs(np.array(ref['value'][:2])-np.array(ref['exact_ab'][i]))) for ref in refs)) for i in range(len(etas))]
    report['fresnel_worst'] = []
    for i,spec in enumerate(specs):
        worst = max(refs,key=lambda ref: np.max(np.abs(np.array(ref['value'][:2])-np.array(ref['exact_ab'][i]))))
        delta = np.array(worst['value'][:2])-np.array(worst['exact_ab'][i])
        report['fresnel_worst'].append({'specular':spec,'nv':worst['nv'],'roughness':worst['roughness'],
                                      'error_ab':delta.tolist(),
                                      'dielectric_output_error':float(np.dot(delta,[.08*spec,1]))})
    report['low_specular_correction'] = []
    for i,spec in enumerate(specs):
        f0 = .08*spec
        scale = min(1.,f0/.04)
        cases = []
        for ref in refs:
            a,b = ref['value'][:2]
            exact_a,exact_b = ref['exact_ab'][i]
            cases.append({'nv':ref['nv'],'roughness':ref['roughness'],
                'dielectric_error_raw':f0*a+b-(f0*exact_a+exact_b),
                'dielectric_error_corrected':f0*a+b*scale-(f0*exact_a+exact_b),
                'metal_channel_errors':{str(c):c*a+b*scale-(c*exact_a+exact_b) for c in (0.,.25,.5,1.)}})
        report['low_specular_correction'].append({'specular':spec,'scale':scale,'cases':cases,
            'max_abs_dielectric_error_raw':max(abs(c['dielectric_error_raw']) for c in cases),
            'max_abs_dielectric_error_corrected':max(abs(c['dielectric_error_corrected']) for c in cases),
            'max_abs_white_metal_error':max(abs(c['metal_channel_errors']['1.0']) for c in cases)})
    report['importance_reference_max_abs_error'] = np.max(np.abs(np.array([
        integrate(ref['nv'],ref['roughness'],args.samples)-ref['value'] for ref in refs])),axis=0).tolist()
    report['karis_max_abs_ess_error'] = float(max(abs(karis(ref['nv'],ref['roughness']).sum()-sum(ref['value'][:2])) for ref in refs))
    report['karis_coat_max_abs_error'] = float(max(abs(np.dot(karis(ref['nv'],ref['roughness']),[.04,1])-ref['value'][2]) for ref in refs))
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    if passed:
        lut = lut.copy()
        lut[:,:,3] = 0  # v3.2: reserved, never Ess_lit in the shipped texture.
        header = REPO_ROOT/'source/source/blender/gpu/intern/gpu_brdf_lut.h'
        lines = ['/* SPDX-License-Identifier: GPL-2.0-or-later */',
                 '/* Generated by tools/debug/bsdf/integrar_brdf.py. Do not edit. */',
                 '/* Row: roughness; column: NoV; cell centers. RGBA: A, B, Ecc, 0 (reserved). */',
                 '#ifndef GPU_BRDF_LUT_H','#define GPU_BRDF_LUT_H',
                 '#define GPU_BRDF_LUT_SIZE %d'%n,
                 'static const float gpu_brdf_lut[GPU_BRDF_LUT_SIZE * GPU_BRDF_LUT_SIZE * 4] = {']
        lines += ['  '+', '.join('%.9ef'%v for v in cell)+',' for cell in lut.reshape(-1,4)]
        lines += ['};','#endif','']
        header.write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps({k:report[k] for k in ('selected_size','fresnel_max_abs_ab_error','karis_max_abs_ess_error','karis_coat_max_abs_error')},indent=2))
    if not passed:
        print('LUT failed criteria; header NOT emitted. See report.json.',flush=True)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
