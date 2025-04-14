import { McpServerAdapter } from "./adapters/mcp-server-adapter.js";
import routes from "./routes.js";

const router = routes();
const app = new McpServerAdapter(router);

app.register({
  name: "memory-bank",
  version: "1.0.0",
});

export default app;
