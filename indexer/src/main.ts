// Plantilla base Subsquid EVM — adaptada de https://github.com/subsquid-labs (evm-example)
// Fase 0: ingiere Transfer/txs recientes de Ethereum y las persiste vía TypeORM.
// TODO Fase 0 salida: mapear también a Neo4j (Bolt) en batch.
import { EvmBatchProcessor } from '@subsquid/evm-processor';
import { TypeormDatabase } from '@subsquid/typeorm-store';

const db = new TypeormDatabase();
const processor = new EvmBatchProcessor()
  .setGateway(process.env.SQD_GATEWAY ?? 'https://v2.archive.subsquid.io/network/ethereum-mainnet')
  .setRpcEndpoint(process.env.RPC_ETH_HTTP ?? 'https://eth.llamarpc.com')
  .setFinalityConfirmation(75)
  .addTransaction({});

processor.run(db, async (ctx) => {
  for (const block of ctx.blocks) {
    for (const tx of block.transactions) {
      ctx.log.info(`tx ${tx.hash} blk=${block.header.height} from=${tx.from} to=${tx.to}`);
      // En Fase 0 el store TypeORM persiste según schema.graphql via codegen.
    }
  }
});
