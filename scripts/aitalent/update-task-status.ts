#!/usr/bin/env tsx
/**
 * 管理用スクリプト: タスクのステータスを直接更新
 * 
 * 使い方:
 *   tsx scripts/update-task-status.ts <taskId> <status>
 * 
 * 例:
 *   tsx scripts/update-task-status.ts t_1766122744120_1 done
 */

import { createSheetsStorage } from "../lib/storage/sheets-repository";

async function main() {
  const [taskId, status] = process.argv.slice(2);

  if (!taskId || !status) {
    console.error("使い方: tsx scripts/update-task-status.ts <taskId> <status>");
    console.error("例: tsx scripts/update-task-status.ts t_1766122744120_1 done");
    process.exit(1);
  }

  if (!["todo", "done", "miss"].includes(status.toLowerCase())) {
    console.error(`エラー: status は todo/done/miss のいずれかを指定してください（指定: ${status}）`);
    process.exit(1);
  }

  console.log(`タスク更新を開始: ${taskId} → ${status}`);

  const storage = createSheetsStorage();

  // 1. タスクが存在するか確認
  const task = await storage.tasks.findById(taskId);
  if (!task) {
    console.error(`エラー: タスクID「${taskId}」は見つかりません`);
    process.exit(1);
  }

  console.log("【更新前】");
  console.log(`  ID: ${task.id}`);
  console.log(`  ステータス: ${task.status}`);
  console.log(`  説明: ${task.description}`);
  console.log(`  優先度: ${task.priority || "-"}`);
  console.log(`  期限: ${task.dueDate || "-"}`);

  // 2. ステータスを更新
  const success = await storage.tasks.updateStatus(taskId, status);
  if (!success) {
    console.error(`エラー: タスクの更新に失敗しました（updateStatus returned false）`);
    process.exit(1);
  }

  // 3. 更新後の状態を確認
  const updated = await storage.tasks.findById(taskId);
  if (!updated) {
    console.error(`エラー: 更新後のタスクが見つかりません（検証失敗）`);
    process.exit(1);
  }

  if (updated.status !== status) {
    console.error(`エラー: ステータスの検証に失敗しました`);
    console.error(`  期待: ${status}`);
    console.error(`  実際: ${updated.status}`);
    process.exit(1);
  }

  console.log("\n【更新後】");
  console.log(`  ID: ${updated.id}`);
  console.log(`  ステータス: ${updated.status}`);
  console.log(`  説明: ${updated.description}`);
  console.log(`  優先度: ${updated.priority || "-"}`);
  console.log(`  期限: ${updated.dueDate || "-"}`);

  console.log("\n✅ タスクの更新に成功しました");
}

main().catch((error) => {
  console.error("予期しないエラーが発生しました:", error);
  process.exit(1);
});
