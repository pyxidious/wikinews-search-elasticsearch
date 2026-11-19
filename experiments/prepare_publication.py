"""Create a new verified source snapshot and local release assets; never uploads or uses Git/ES."""
from __future__ import annotations
import argparse,ast,hashlib,json,os,shutil,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
RAW_NAME='performance-raw-20261118.zip'
KIT_NAME='wikinews-reproducibility-kit-20261119.zip'
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(path,value):
 payload=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
 with Path(path).open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
def source_files(repo):
 names=['.gitignore','README.md','TESTING.md','requirements.txt','requirements-dev.txt','pytest.ini','docker-compose.yml']
 files=[repo/n for n in names if (repo/n).is_file()]
 for dirname in ['.github','wikinews_search','tests','scripts','experiments']:
  for p in (repo/dirname).rglob('*'):
   rel=p.relative_to(repo)
   if not p.is_file() or any(x in rel.parts for x in ['__pycache__','reproducibility-inputs']):continue
   if p.is_symlink():raise ValueError('Unexpected symbolic link: '+str(p))
   if p.suffix=='.zip' or p.stat().st_size>20*1024*1024:raise ValueError('Unexpected archive/large file in source tree: '+str(p))
   files.append(p)
 return sorted(files,key=lambda p:p.relative_to(repo).as_posix())
def copy_verified(source,destination,expected):
 destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
 with Path(source).open('rb') as src,destination.open('xb') as dst:
  shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
 if sha(destination)!=expected:raise ValueError('Copied bytes differ: '+str(destination))
def snapshot(repo,target):
 target=Path(target).resolve()
 if target.exists() or target.is_relative_to(repo.resolve()):raise ValueError('Use a new snapshot directory outside the repository')
 files=source_files(repo);expected={p.relative_to(repo).as_posix():sha(p) for p in files}
 target.mkdir(parents=True)
 for p in files:copy_verified(p,target/p.relative_to(repo),expected[p.relative_to(repo).as_posix()])
 for name,digest in expected.items():
  p=target/name
  if sha(p)!=digest:raise ValueError('Snapshot checksum mismatch: '+name)
  if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'),filename=name)
 save(target/'SOURCE_SHA256.json',{'files':expected,'all_copies_verified':True,'python_sources_parse':True,'original_inputs_excluded':True,'full_article_bodies_excluded':True})
 return expected
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--raw-archive',type=Path);parser.add_argument('--snapshot-only',action='store_true');args=parser.parse_args();dest=args.destination.resolve()
 if dest.exists() or dest.is_relative_to(REPO):parser.error('Destination must be new and outside repository; no overwrite')
 if args.snapshot_only:
  records=snapshot(REPO,dest);print(json.dumps({'snapshot':str(dest),'files_verified':len(records)}));return
 if not args.raw_archive:parser.error('--raw-archive is required for release preparation')
 spec=json.loads((REPO/'experiments/performance-20261118/RAW_DATA.json').read_text(encoding='utf-8'))
 if sha(args.raw_archive)!=spec['archive_sha256']:raise ValueError('Raw archive SHA mismatch')
 dest.mkdir(parents=True);records=snapshot(REPO,dest/'source-snapshot')
 raw=dest/RAW_NAME;copy_verified(args.raw_archive,raw,spec['archive_sha256'])
 kit=dest/KIT_NAME
 with zipfile.ZipFile(kit,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name in [*records,'SOURCE_SHA256.json']:z.write(dest/'source-snapshot'/name,name)
 with kit.open('r+b') as f:f.flush();os.fsync(f.fileno())
 with zipfile.ZipFile(kit) as z:
  if z.testzip() is not None:raise ValueError('Kit CRC failure')
  for name,digest in records.items():
   if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('Kit entry mismatch: '+name)
 sums={name:sha(dest/name) for name in [KIT_NAME,RAW_NAME]}
 with (dest/'SHA256SUMS').open('x',encoding='ascii',newline='\n') as f:
  for name,digest in sums.items():f.write(digest+'  '+name+'\n')
  f.flush();os.fsync(f.fileno())
 save(dest/'RELEASE_MANIFEST.json',{'uploaded':False,'destination':str(dest),'assets':{name:{'sha256':digest,'bytes':(dest/name).stat().st_size} for name,digest in sums.items()},'source_files_verified':len(records),'original_source_archives_included':False,'application_modified':False})
 print(json.dumps({'destination':str(dest),'source_files_verified':len(records),'assets':sums},indent=2))
if __name__=='__main__':main()
