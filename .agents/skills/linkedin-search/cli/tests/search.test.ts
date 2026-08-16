import { afterEach, describe, expect, test } from "bun:test";
import { buildSearchUrl, runSearch } from "../src/commands/search";
import { workTypeFlag } from "../src/helpers";

const originalFetch = globalThis.fetch;
const originalStdoutWrite = process.stdout.write;

function searchCard(id: string, title: string): string {
  return `<li>
    <div data-entity-urn="urn:li:jobPosting:${id}">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/${id}"></a>
      <h3 class="base-search-card__title">${title}</h3>
    </div>
  </li>`;
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  process.stdout.write = originalStdoutWrite;
});

describe("runSearch", () => {
  test("--limit 0 emits zero results", async () => {
    globalThis.fetch = (async () => new Response(searchCard("123456", "Engineer"))) as typeof fetch;

    let stdout = "";
    process.stdout.write = ((chunk: string | Uint8Array) => {
      stdout += chunk.toString();
      return true;
    }) as typeof process.stdout.write;

    const code = await runSearch({
      location: "Copenhagen, Denmark",
      jobage: 9999,
      page: 1,
      limit: 0,
      format: "json",
    });

    expect(code).toBe(0);
    expect(JSON.parse(stdout).results).toHaveLength(0);
  });

  test("--remote remote sets f_WT=2 and can use location=Remote", () => {
    expect(workTypeFlag("remote")).toBe("2");
    const url = buildSearchUrl({
      query: "engineer",
      location: "Remote",
      jobage: 14,
      remote: "remote",
      page: 1,
      format: "json",
    });
    expect(url).toContain("f_WT=2");
    expect(url).toContain("location=Remote");
    expect(url).toContain("keywords=engineer");
  });
});
