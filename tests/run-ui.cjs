// One portable entry point; each suite owns and closes its browser/server.
const {spawnSync}=require('node:child_process'),fs=require('node:fs'),path=require('node:path');
const suites=['state_modules.cjs','task_controller.cjs','optics_v09.cjs',...fs.readdirSync(__dirname).filter(n=>/^ui_.*\.cjs$/.test(n)).sort()];
let failures=[];
for(const name of suites){
 console.log('\n--- '+name+' ---');
 const result=spawnSync(process.execPath,[path.join(__dirname,name)],{cwd:path.resolve(__dirname,'..'),stdio:'inherit'});
 if(result.error)console.error(result.error);
 if(result.status!==0)failures.push(name);
}
console.log(`\n${suites.length-failures.length}/${suites.length} suites passed`);
if(failures.length){console.error('Failed: '+failures.join(', '));process.exitCode=1}
