/** Mesta Nazorat Bot — asosiy servis (9143549c), Hisobchi emas */

const TOKEN = (process.env.RAILWAY_TOKEN || "").trim();
if (!TOKEN) {
  console.error("RAILWAY_TOKEN yo'q");
  process.exit(1);
}

const API = "https://backboard.railway.com/graphql/v2";

const MESTA = {
  projectId: "07249ace-db4b-44c1-8545-f1a5f1ea29cc",
  environmentId: "f7c5c3ad-6ea3-454d-8416-f1121cf04292",
  serviceId: "9143549c-56c5-4160-aedb-026a757d61f3",
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

async function upsertEnv(variables) {
  await gql(
    `mutation($input: VariableCollectionUpsertInput!) { variableCollectionUpsert(input: $input) }`,
    {
      input: {
        ...MESTA,
        variables,
        replace: false,
      },
    }
  );
}

async function deploy(commitSha) {
  const data = await gql(
    `mutation($e:String!, $s:String!, $c:String!) {
      serviceInstanceDeployV2(environmentId: $e, serviceId: $s, commitSha: $c)
    }`,
    { e: MESTA.environmentId, s: MESTA.serviceId, c: commitSha }
  );
  console.log("deploy:", data.serviceInstanceDeployV2);
}

async function main() {
  const botToken = (process.env.MESTA_BOT_TOKEN || "").trim();
  const env = { MINUTES_PER_POSITION: "4", TZ: "Asia/Tashkent" };
  if (botToken) {
    env.BOT_TOKEN = botToken;
    console.log("env: BOT_TOKEN tiklanadi");
  } else {
    console.log("env: BOT_TOKEN o'zgarmaydi (MESTA_BOT_TOKEN berilmagan)");
  }
  await upsertEnv(env);

  const sha = process.argv[2];
  if (!sha) throw new Error("commit SHA kerak: node railway-deploy-mesta.mjs <sha>");
  await deploy(sha);
}

main().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
