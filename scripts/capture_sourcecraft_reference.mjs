import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

const refDir = path.resolve('docs/sourcecraft-reference');
if (!fs.existsSync(refDir)) {
  fs.mkdirSync(refDir, { recursive: true });
}

const edgePath = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const browserExe = fs.existsSync(edgePath) ? edgePath : chromePath;

console.log('Capturing SourceCraft live references using:', browserExe);

const tasks = [
  {
    name: 'sourcecraft-reference-light.png',
    url: 'https://sourcecraft.dev',
    args: ['--window-size=1440,900']
  },
  {
    name: 'sourcecraft-reference-repository.png',
    url: 'https://sourcecraft.dev/find/repositories',
    args: ['--window-size=1440,900']
  },
  {
    name: 'sourcecraft-reference-dark.png',
    url: 'https://sourcecraft.dev',
    args: ['--window-size=1440,900', '--force-dark-mode', '--enable-features=WebContentsForceDark']
  }
];

for (const task of tasks) {
  const dest = path.join(refDir, task.name);
  console.log(`Capturing ${task.name} from ${task.url}...`);
  await new Promise((resolve) => {
    const proc = spawn(browserExe, [
      '--headless=new',
      '--disable-gpu',
      '--hide-scrollbars',
      ...task.args,
      '--virtual-time-budget=6000',
      `--screenshot=${dest}`,
      task.url
    ]);
    const timer = setTimeout(() => {
      proc.kill();
      resolve();
    }, 12000);
    proc.on('close', () => {
      clearTimeout(timer);
      resolve();
    });
  });

  if (fs.existsSync(dest)) {
    const stat = fs.statSync(dest);
    console.log(`✓ ${task.name} created (${stat.size} bytes)`);
  } else {
    console.error(`✗ FAILED to create ${task.name}`);
  }
}

console.log('Reference capture run finished.');
