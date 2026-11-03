// Pure queries must run without a DOM and must not share session state.
const assert=require('node:assert/strict'),{pathToFileURL}=require('node:url'),path=require('node:path');
(async()=>{
 const {createState}=await import(pathToFileURL(path.resolve(__dirname,'../pianji/ui/core/state.js')));
 const {createQueries}=await import(pathToFileURL(path.resolve(__dirname,'../pianji/ui/core/queries.js')));
 const s=createState(),other=createState(),q=createQueries(s);
 s.selected.sd.add('pair');s.sourcePhotos.push({id:'pair',relative_dirs:['DCIM/JPEG','DCIM/RAW'],files:[{kind:'jpeg'},{kind:'raw'}]},{id:'single',relative_dir:'other',files:[{kind:'jpeg'}]});
 assert.equal(other.selected.sd.size,0);assert.equal(other.sourcePhotos.length,0);
 assert.deepEqual(q.folderPaths(),['','DCIM','DCIM/JPEG','DCIM/RAW','other']);
 s.sourceFolder='DCIM/RAW';s.format='raw';assert.deepEqual(q.visible().map(p=>p.id),['pair']);
 s.sourceFolder='*';s.format='jpeg';s.onlySelected=true;assert.deepEqual(q.visible().map(p=>p.id),['pair']);assert.equal(q.visible(true).length,2);
 s.view='library';s.activity='a';s.person='alice';s.onlySelected=false;s.format='all';s.stage='exports';
 s.photos=[{id:'a1',activity_id:'a',person_id:'alice',edited:1,primary_export_id:'x',captured_at:'2026-11-01T12:00:00',assets:[{kind:'jpeg'}]},{id:'a2',activity_id:'a',person_id:'bob',edited:0,assets:[{kind:'raw'}]},{id:'b1',activity_id:'b',person_id:'alice',edited:1,primary_export_id:'y',assets:[{kind:'jpeg'}]}];
 assert.deepEqual(q.visible().map(p=>p.id),['a1']);s.date='unknown';assert.equal(q.visible().length,0);
 s.date='all';s.person='all';s.stage='pending';assert.deepEqual(q.visible().map(p=>p.id),['a2']);
 s.people=[{id:'alice',name:'Alice'},{id:'bob',name:'Bob'}];s.stage='all';
 assert.deepEqual(q.libraryFolders().map(f=>[f.key,f.count,f.examples[0].id]),[['alice',1,'a1'],['bob',1,'a2']]);
 s.selected.library.add('a1');s.current='a1';s.anchor.library='a1';s.lastOperation={id:'op'};s.onlySelected=true;
 q.resetLibrarySelection();assert.equal(s.selected.library.size,0);assert.equal(s.current,null);assert.equal(s.anchor.library,null);assert.equal(s.lastOperation,null);assert.equal(s.onlySelected,false);assert(s.selected.sd.has('pair'));
 console.log('PASS isolated state, source pairing, combined filters, folder examples and selection reset');
})().catch(e=>{console.error(e);process.exitCode=1});
