// IndexNow proves ownership by fetching `https://<host>/<key>.txt`, whose body
// must be exactly the key, so the key is public by design and lives in source.
// Keep it 32 hex characters: `privacy.ts` rejects any 64-hex run as an artifact
// hash, and a leading digit keeps the file first under both the `Array#sort`
// and `localeCompare` orderings that `check-generated.ts` and `assertDistSafe`
// compare against `expectedDistFiles`.
export const indexNowKey = "5aa51b23de7a6a0e2b96d261c66a1d11";
export const indexNowKeyFile = `${indexNowKey}.txt`;
