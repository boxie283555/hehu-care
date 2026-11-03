const {spawnSync}=require('node:child_process'),path=require('node:path'),fs=require('node:fs');
const root=path.resolve(__dirname,'..');
const venv=path.join(root,'data/venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const PYTHON=process.env.HEHU_TEST_PYTHON||(fs.existsSync(venv)?venv:process.platform==='win32'?'python':'python3');
function database(args){const r=spawnSync(PYTHON,[path.join(root,'tools/test_database.py'),...args],{encoding:'utf8'});if(r.status!==0)throw Error('PostgreSQL test schema operation failed: '+r.stderr);return r.stdout.trim();}
function createSchema(){return database(['create']);}
function dropSchema(schema){database(['drop',schema]);}
async function stopServer(server){if(server.exitCode!==null||server.signalCode!==null)return;await new Promise(resolve=>{server.once('exit',resolve);server.kill();});}
module.exports={PYTHON,createSchema,dropSchema,stopServer};
