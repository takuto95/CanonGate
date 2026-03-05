import "dotenv/config";
import { repairSheets } from "../lib/tools/repair-sheets-misalignment";

function parseArgs(argv: string[]) {
  const args = new Set(argv);
  const apply = args.has("--apply");

  const limitFlagIdx = argv.findIndex(a => a === "--limit");
  const limitRaw = limitFlagIdx >= 0 ? argv[limitFlagIdx + 1] : null;
  const limit = limitRaw ? Math.max(1, Number(limitRaw)) : Number.POSITIVE_INFINITY;

  const sheetFlagIdx = argv.findIndex(a => a === "--sheet");
  const sheet = sheetFlagIdx >= 0 ? (argv[sheetFlagIdx + 1] || "").trim() : "";

  return { apply, limit, sheet };
}

async function main() {
  const { apply, limit, sheet } = parseArgs(process.argv.slice(2));

  const summaries = await repairSheets({ apply, limit, sheet });
  for (const s of summaries) {
    console.log(
      `[${s.sheetName}] scanned=${s.scanned} aligned=${s.aligned} repaired=${s.repaired}${s.applied ? " (applied)" : " (dry-run)"} skipped=${s.skipped}${s.limited ? " (limited)" : ""}`
    );
  }
}

main().catch(err => {
  console.error("[repair-sheets-misalignment] failed:", err?.message || err);
  process.exit(1);
});

