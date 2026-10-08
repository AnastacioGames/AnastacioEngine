"""Install optional Steam DLLs and reusable component in an existing game directory.
No SDK headers copied, no executable replaced, no credentials or AppID invented.
Development --appid writes steam_appid.txt; do not include that file in published depots.
"""
import argparse
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('--target', type=Path, required=True)
parser.add_argument('--complement', type=Path, default=Path('build-steam'))
parser.add_argument('--appid', type=int, help='Development only: write steam_appid.txt')
parser.add_argument('--version', default='2.79')
args = parser.parse_args()
if not args.target.is_dir(): parser.error('Target must be an existing game directory')
if args.appid is not None and not 0 < args.appid <= 2**32-1: parser.error('Invalid AppID')
for name in ('AnastacioSteam.dll', 'steam_api64.dll'):
    if not (args.complement/name).is_file(): parser.error('Missing complement file: ' + name)
if Path(args.version).name != args.version or args.version in ('.', '..'): parser.error('Invalid version directory')
destination = args.target/'complements'/'steam'
destination.mkdir(parents=True, exist_ok=True)
for name in ('AnastacioSteam.dll', 'steam_api64.dll'):
    shutil.copy2(args.complement/name, destination/name)
package = Path(__file__).resolve().parents[1]/'source/release/scripts/modules/anastacio_network'
shutil.copytree(package, args.target/args.version/'scripts/modules/anastacio_network',
                dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
if args.appid is not None:
    (args.target/'steam_appid.txt').write_text(str(args.appid)+'\n', encoding='ascii')
print('Optional complement installed in', destination)
