// Responsibility: compose configuration, feature services, tools, and application entry points.
import {loadConfig} from './config.mjs';
import {Store} from './core/storage.mjs';
import {Jobs} from './core/jobs.mjs';
import {Harness} from './core/harness.mjs';
import {Library} from './research/library.mjs';
import {paperTools} from './research/tools.mjs';
import {Workspace} from './tools/workspace.mjs';
import {Discovery} from './research/discovery.mjs';
import {Reviews} from './research/reviews.mjs';
import {Translations} from './translation/service.mjs';
import {serve} from './web/server.mjs';
import {runCli} from './cli.mjs';

const config = loadConfig();
const store = new Store(config);
const jobs = new Jobs(config,store);
const library = new Library(config,store);
const workspace = new Workspace(config);
const discovery = new Discovery(config,store,library);
const reviews = new Reviews(config,library,workspace);
const translations = new Translations(config,store,library,discovery);
const tools = [...paperTools(library,discovery),...reviews.tools(),...workspace.tools()];
const harness = new Harness(config,store,tools);
const app = {config,store,jobs,library,workspace,discovery,reviews,harness,translations};
const args = process.argv.slice(2);
if (!args.length || args[0] === 'serve') serve(app);
else await runCli(app,args).catch(error=>{console.error(error.message);process.exitCode=1;});
