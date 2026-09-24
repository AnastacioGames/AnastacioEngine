#!/usr/bin/env python3
"""Gera o APK Android a partir de um pacote do export Web (A3 de docs/android-export-plan.md).

A logica fica em range_web/android.py, a mesma usada pelo painel Android do editor; este script
serve para gerar e testar pelo terminal, sem abrir o editor.

Exemplos:
  python tools/web/package-android.py --web build-web/dist/First_Person --config android-export.json
  python tools/web/package-android.py --web build-web/dist/First_Person --config android-export.json --install

Sem --config, --app-id e --name bastam (o resto usa os padroes). Saida em --out-dir (padrao
build-android/<nome do pacote Web>): o APK, android-export.json usado, android-report.json e gradle.log.

Release assinado (a chave fica fora do git; a senha vem de RANGE_ANDROID_KEYSTORE_PASSWORD ou e pedida):
  python tools/web/package-android.py --create-keystore %USERPROFILE%/RangeAndroidKeys/jogo.jks --name Jogo
  python tools/web/package-android.py --web ... --config android-export.json --build-type release       --keystore %USERPROFILE%/RangeAndroidKeys/jogo.jks
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "source" / "release" / "scripts" / "modules"))

from range_web import android  # noqa: E402


def password_from_env_or_prompt(confirm=False):
    password = os.environ.get(android.PASSWORD_ENV)
    if password:
        return password
    password = getpass.getpass("Senha da chave: ")
    if confirm and getpass.getpass("Repita a senha: ") != password:
        sys.exit("ERRO: as senhas nao conferem.")
    return password


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--web", type=Path, help="pasta do pacote gerado pelo export Web")
    ap.add_argument("--config", type=Path, help="android-export.json")
    ap.add_argument("--app-id", help="applicationId (sobrepoe o do --config)")
    ap.add_argument("--name", help="nome do app (sobrepoe o do --config)")
    ap.add_argument("--version-name", help="versionName (sobrepoe o do --config)")
    ap.add_argument("--version-code", type=int, help="versionCode (sobrepoe o do --config)")
    ap.add_argument("--icon", help="icone PNG (sobrepoe o do --config)")
    ap.add_argument("--orientation", choices=sorted(android.ORIENTATIONS))
    ap.add_argument("--build-type", choices=android.BUILD_TYPES)
    ap.add_argument("--keystore", help="chave do release (sobrepoe a do --config)")
    ap.add_argument("--key-alias", help="alias da chave (sobrepoe o do --config; padrao upload)")
    ap.add_argument("--create-keystore", metavar="ARQUIVO", help="cria a chave do release e sai")
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--jdk", default="", help="pasta do JDK, se nao houver JAVA_HOME nem Android Studio")
    ap.add_argument("--sdk", default="", help="pasta do Android SDK, se nao houver ANDROID_HOME nem Android Studio")
    ap.add_argument("--install", action="store_true", help="instala no aparelho pelo adb e abre o jogo")
    args = ap.parse_args()
    if not args.web and not args.create_keystore:
        ap.error("informe --web (ou --create-keystore)")

    config = android.load_config(args.config) if args.config else dict(android.DEFAULTS)
    overrides = {"applicationId": args.app_id, "appName": args.name, "versionName": args.version_name,
                 "versionCode": args.version_code, "orientation": args.orientation,
                 "buildType": args.build_type,
                 "icon": os.path.abspath(args.icon) if args.icon else None,
                 "keystore": os.path.abspath(args.keystore) if args.keystore else None,
                 "keyAlias": args.key_alias}
    config.update({k: v for k, v in overrides.items() if v is not None})
    config["keyAlias"] = config.get("keyAlias") or "upload"

    try:
        toolchain = android.find_toolchain(args.jdk, args.sdk)
        if args.create_keystore:
            password = password_from_env_or_prompt(confirm=True)
            android.create_keystore(os.path.abspath(args.create_keystore), config["keyAlias"], password,
                                    config.get("appName") or "", toolchain)
            return
        out_dir = args.out_dir or REPO_ROOT / "build-android" / args.web.resolve().name
        password = password_from_env_or_prompt() if config.get("buildType") == "release" else None
        apk = android.build_apk(str(args.web), config, str(out_dir), toolchain, password=password)
        if args.install:
            android.install_apk(apk, config["applicationId"], toolchain)
            print("Instalado e aberto no aparelho.")
    except android.AndroidError as exc:
        sys.exit("ERRO: %s" % exc)


if __name__ == "__main__":
    main()
