/** Hisobchi Bot (inventarizatsiya) — Railway deploy + Ozodbek ID tekshiruvi */

const TOKEN = (process.env.RAILWAY_TOKEN || "").trim();
if (!TOKEN) {
  console.error("RAILWAY_TOKEN yo'q");
  process.exit(1);
}

const API = "https://backboard.railway.com/graphql/v2";

const HISOBCHI = {
  projectId: "07249ace-db4b-44c1-8545-f1a5f1ea29cc",
  environmentId: "f7c5c3ad-6ea3-454d-8416-f1121cf04292",
  serviceId: "1309ba4f-7493-4f52-87f4-b7ec982e77e4",
};

async function gql(query, variables = {}) {
  const res = await fetch(API, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, variables }),
  });
  const data = await res.json();
  if (data.errors?.length) {
    throw new Error(data.errors.map((e) => e.message).join("; "));
  }
  return data.data;
}

async function deployLatest({ environmentId, serviceId, label }) {
  const q = `mutation($serviceId: String!, $environmentId: String!, $latestCommit: Boolean) {
    serviceInstanceDeploy(serviceId: $serviceId, environmentId: $environmentId, latestCommit: $latestCommit)
  }`;
  const data = await gql(q, { serviceId, environmentId, latestCommit: true });
  console.log(`deploy ${label}:`, data.serviceInstanceDeploy ? "OK (latest commit)" : "?");
}

async function main() {
  await deployLatest({ ...HISOBCHI, label: "hisobchi-bot" });
}

main().catch((e) => {
  console.error("deploy failed:", e.message);
  process.exit(1);
});
