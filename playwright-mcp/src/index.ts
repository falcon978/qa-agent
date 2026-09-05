import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { chromium } from "playwright";
import * as fs from "fs/promises";
import * as path from "path";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

let globalBrowser: any = null;
let globalPage: any = null;

async function getPage() {
  if (!globalBrowser) {
    globalBrowser = await chromium.launch({ headless: true });
  }
  if (!globalPage) {
    globalPage = await globalBrowser.newPage();
  }
  return globalPage;
}

const server = new Server(
  {
    name: "playwright-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "explore_url",
        description: "Navigates to a URL and returns page title and basic info.",
        inputSchema: {
          type: "object",
          properties: {
            url: { type: "string" },
          },
          required: ["url"],
        },
      },
      {
        name: "reset_browser",
        description: "Closes the current browser session. Useful if the browser is stuck in a bad state.",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "execute_playwright_commands",
        description: "Execute atomic Playwright commands (goto, fill, click, extract_dom) in a single session.",
        inputSchema: {
          type: "object",
          properties: {
            base_url: { type: "string" },
            commands: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  action: { type: "string", enum: ["goto", "fill", "click", "extract_dom"] },
                  url: { type: "string" },
                  selector: { type: "string" },
                  value: { type: "string" }
                },
                required: ["action"]
              }
            }
          },
          required: ["base_url", "commands"],
        },
      },
      {
        name: "run_test_suite",
        description: "Writes Playwright test scripts to disk and executes them, returning the JSON report.",
        inputSchema: {
          type: "object",
          properties: {
            files: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  filename: { type: "string" },
                  code: { type: "string" },
                },
                required: ["filename", "code"],
              },
            },
            run_id: { type: "string" },
          },
          required: ["files"],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "reset_browser") {
    if (globalBrowser) {
      await globalBrowser.close().catch(() => {});
      globalBrowser = null;
      globalPage = null;
    }
    return {
      content: [{ type: "text", text: "Browser reset successfully." }],
    };
  }

  if (name === "execute_playwright_commands") {
    const baseUrl = String(args?.base_url);
    const commands = args?.commands as any[];
    try {
      const page = await getPage();
      
      const parsedBase = new URL(baseUrl);
      let domResult = "";
      
      for (const cmd of commands) {
        if (cmd.action === "goto") {
          const targetUrl = new URL(cmd.url);
          if (targetUrl.hostname !== parsedBase.hostname) {
            throw new Error(`Security Exception: Navigation to ${targetUrl.hostname} is forbidden.`);
          }
          await page.goto(cmd.url, { waitUntil: "domcontentloaded" });
        } else if (cmd.action === "fill") {
          await page.fill(cmd.selector, String(cmd.value));
        } else if (cmd.action === "click") {
          await page.click(cmd.selector);
          // Wait briefly for any potential navigation/rendering
          await page.waitForTimeout(500); 
        } else if (cmd.action === "extract_dom") {
          const domData = await page.evaluate(() => {
            const elements = Array.from(document.querySelectorAll('input, button, a, [role="button"]'));
            return elements.map(el => {
              return {
                tag: el.tagName.toLowerCase(),
                id: el.id,
                className: el.className,
                text: (el as HTMLElement).innerText?.trim().substring(0, 50) || '',
                placeholder: (el as HTMLInputElement).placeholder || '',
                href: (el as HTMLAnchorElement).href || ''
              };
            }).filter(el => el.id || el.className || el.text || el.placeholder);
          });
          domResult = JSON.stringify(domData, null, 2);
        }
      }
      
      return {
        content: [{ type: "text", text: `Execution successful.\nDOM:\n${domResult}` }],
      };
    } catch (e: any) {
      return {
        isError: true,
        content: [{ type: "text", text: `Error executing commands: ${e.message}` }],
      };
    }
  }

  if (name === "explore_url") {
    const url = String(args?.url);
    try {
      const page = await getPage();
      await page.goto(url, { waitUntil: "domcontentloaded" });
      const title = await page.title();
      
      // Extract simplified DOM (inputs, buttons, links)
      const domData = await page.evaluate(() => {
        const elements = Array.from(document.querySelectorAll('input, button, a'));
        return elements.map(el => {
          return {
            tag: el.tagName.toLowerCase(),
            id: el.id,
            className: el.className,
            text: (el as HTMLElement).innerText?.trim().substring(0, 50) || '',
            placeholder: (el as HTMLInputElement).placeholder || '',
            href: (el as HTMLAnchorElement).href || ''
          };
        }).filter(el => el.id || el.className || el.text || el.placeholder);
      });
      
      const domString = JSON.stringify(domData, null, 2);
      
      return {
        content: [{ type: "text", text: `Title: ${title}\nInteractive Elements:\n${domString}` }],
      };
    } catch (e: any) {
      return {
        isError: true,
        content: [{ type: "text", text: `Error exploring URL: ${e.message}` }],
      };
    }
  }

  if (name === "run_test_suite") {
    const files = args?.files as { filename: string; code: string }[];
    const runId = args?.run_id ? String(args.run_id) : `run_${Date.now()}`;
    const testDir = path.join(process.cwd(), "playwright-mcp", "test-result", runId);
    
    try {
      await fs.mkdir(testDir, { recursive: true });
      for (const file of files) {
        await fs.writeFile(path.join(testDir, file.filename), file.code);
      }
      
      // Run playwright test using the locally installed module in playwright-mcp
      let output = "";
      try {
        const mcpDir = path.join(process.cwd(), "playwright-mcp");
        const { stdout, stderr } = await execAsync(`npx playwright test "${testDir}" --reporter=json`, { cwd: mcpDir });
        output = stdout || stderr;
      } catch (execError: any) {
        // Playwright exits with code 1 if tests fail, which throws here
        output = execError.stdout || execError.stderr;
      }
      
      return {
        content: [{ type: "text", text: output }],
      };
    } catch (e: any) {
      return {
        isError: true,
        content: [{ type: "text", text: `Error running test suite: ${e.message}` }],
      };
    } finally {
      // Do not clean up testDir so the user can inspect the generated files
    }
  }

  throw new Error(`Tool not found: ${name}`);
});

async function run() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Playwright MCP server running on stdio");
}

run().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
