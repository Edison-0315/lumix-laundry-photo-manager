const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../.superpowers/ui-artifacts');
module.exports=name=>{fs.mkdirSync(root,{recursive:true});return path.join(root,name)};
