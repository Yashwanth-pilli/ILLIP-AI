import * as vscode from "vscode";
import { IllipChatPanel } from "./chatPanel";

export function activate(context: vscode.ExtensionContext) {
  context.subscriptions.push(
    vscode.commands.registerCommand("illip.openChat", () => {
      IllipChatPanel.createOrShow(context.extensionUri);
    }),

    vscode.commands.registerCommand("illip.explainSelection", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const selection = editor.selection;
      const code = editor.document.getText(selection);
      if (!code.trim()) {
        vscode.window.showWarningMessage("Select some code first.");
        return;
      }
      const lang = editor.document.languageId;
      IllipChatPanel.createOrShow(context.extensionUri);
      IllipChatPanel.sendMessage(`Explain this ${lang} code:\n\`\`\`${lang}\n${code}\n\`\`\``);
    }),

    vscode.commands.registerCommand("illip.askAboutFile", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const filename = editor.document.fileName.split(/[\\/]/).pop() ?? "file";
      const content = editor.document.getText().slice(0, 3000);
      const lang = editor.document.languageId;
      const question = await vscode.window.showInputBox({
        prompt: `Ask ILLIP AI about ${filename}`,
        placeHolder: "What does this file do?",
      });
      if (!question) return;
      IllipChatPanel.createOrShow(context.extensionUri);
      IllipChatPanel.sendMessage(
        `File: ${filename}\n\`\`\`${lang}\n${content}\n\`\`\`\n\nQuestion: ${question}`
      );
    }),

    vscode.commands.registerCommand("illip.fixCode", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const selection = editor.selection;
      const code = editor.document.getText(selection.isEmpty ? undefined : selection);
      if (!code.trim()) {
        vscode.window.showWarningMessage("Select some code to fix, or open a file.");
        return;
      }
      const lang = editor.document.languageId;
      IllipChatPanel.createOrShow(context.extensionUri);
      IllipChatPanel.sendMessage(
        `Fix this ${lang} code. Return only the fixed code with a brief explanation of what was wrong:\n\`\`\`${lang}\n${code.slice(0, 4000)}\n\`\`\``
      );
    }),

    vscode.commands.registerCommand("illip.generateTests", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const selection = editor.selection;
      const code = editor.document.getText(selection.isEmpty ? undefined : selection);
      if (!code.trim()) {
        vscode.window.showWarningMessage("Select some code or open a file to generate tests for.");
        return;
      }
      const lang = editor.document.languageId;
      IllipChatPanel.createOrShow(context.extensionUri);
      IllipChatPanel.sendMessage(
        `Generate unit tests for this ${lang} code. Use the standard test framework for ${lang} (pytest for Python, jest for JS/TS, etc.):\n\`\`\`${lang}\n${code.slice(0, 4000)}\n\`\`\``
      );
    }),

    vscode.commands.registerCommand("illip.reviewCode", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const selection = editor.selection;
      const code = editor.document.getText(selection.isEmpty ? undefined : selection);
      if (!code.trim()) {
        vscode.window.showWarningMessage("Select code to review.");
        return;
      }
      const lang = editor.document.languageId;
      IllipChatPanel.createOrShow(context.extensionUri);
      IllipChatPanel.sendMessage(
        `Review this ${lang} code for bugs, security issues, and improvements. Be concise:\n\`\`\`${lang}\n${code.slice(0, 4000)}\n\`\`\``
      );
    })
  );
}

export function deactivate() {}
