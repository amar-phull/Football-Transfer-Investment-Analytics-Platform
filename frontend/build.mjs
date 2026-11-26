import {copyFileSync} from 'node:fs';

for (const [source, target] of [
  ['index.html','index.html'],
  ['src/style.css','style.css'],
  ['node_modules/react/umd/react.production.min.js','react.js'],
  ['node_modules/react-dom/umd/react-dom.production.min.js','react-dom.js']
]) copyFileSync(source,'dist/'+target);
