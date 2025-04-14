#!/usr/bin/env node

import app from "./protocols/mcp/app.js";

app.start().catch((error) => {
  console.error(error);
  process.exit(1);
});
