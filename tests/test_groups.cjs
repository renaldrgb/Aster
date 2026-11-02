const fs=require('fs'),vm=require('vm'),assert=require('assert');
const sandbox={document:{addEventListener(){}}};vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('static/groups.js','utf8'),sandbox);
const tasks=[{id:'1',source_id:'class-a:doc',course:'A',title:'Q1',done:1},{id:'2',source_id:'class-a:doc',course:'A',title:'Q2',done:0},{id:'3',source_id:'class-b:doc',course:'B',title:'Q3',done:0}];
const groups=sandbox.groupSchoolwork(tasks,[{id:'class-a:doc',title:'Lesson one',url:'https://example.org'}]);
assert.equal(groups.length,2);assert.equal(groups[0].tasks.length,2);assert.equal(groups[0].title,'Lesson one');assert.equal(groups[0].tasks[0].done,1);assert.equal(tasks.length,3);
console.log('Document grouping and completion preservation passed.');
