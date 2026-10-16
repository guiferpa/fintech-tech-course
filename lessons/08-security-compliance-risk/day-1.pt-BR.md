# Módulo 8, segunda-feira: hash, criptografia, chaves e mTLS

[Módulo 8](../../modules/08-security-compliance-risk.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Uma carteira digital guarda coisas que machucam pessoas quando vazam: números de CPF, telefones, credenciais do banco parceiro, as chaves privadas que assinam seus webhooks. Ela também envia instruções de pagamento por redes que você não controla. Um atacante que lê um dump do seu banco de dados, ou que se coloca entre você e o banco parceiro, não deveria conseguir nada útil.

Criptografia é a ferramenta para isso, mas a maioria dos incidentes reais não vem de algoritmos quebrados. Vem da ferramenta errada para o trabalho (criptografar uma senha, fazer hash de um CPF que você precisa ler de volta), de chaves guardadas ao lado dos dados que protegem e de chaves que ninguém sabe rotacionar. Esta aula trata de escolher a primitiva certa e, acima de tudo, de gerenciar chaves. O TCM de quinta-feira pede que você rotacione uma chave de assinatura com um cliente ativo e zero falhas, então o ciclo de vida da chave é a parte a dominar.

## 1. Quatro ferramentas que as pessoas confundem

*Fonte principal: OWASP, "Cryptographic Storage Cheat Sheet", seções "Introduction" e "Algorithms". As linhas de HMAC e assinatura vêm da prática geral de criptografia, não do cheat sheet, que não trata de HMAC.*

Comece perguntando o que quem lê o dado precisa fazer com ele. Essa pergunta escolhe a primitiva.

| Ferramenta | Chave? | Reversível? | Responde à pergunta | Exemplo na carteira |
| --- | --- | --- | --- | --- |
| Hash (SHA-256) | Não | Não | "São os mesmos bytes de antes?" | Impressão digital de um documento enviado |
| Hash de senha (Argon2id, bcrypt) | Não, mas com salt e lento de propósito | Não | "O usuário digitou a senha certa?" | Senha de login, PIN de transação |
| HMAC (HMAC-SHA256) | Segredo compartilhado | Não | "Alguém que tem o segredo produziu isto, sem alteração?" | Assinatura de webhook com segredo compartilhado |
| Assinatura digital (Ed25519, ECDSA) | Chave privada assina, chave pública verifica | Não | "Quem tem a chave privada produziu isto, sem alteração?" | Assinatura de webhook verificável por um endpoint público |
| Criptografia (AES-256-GCM) | Chave secreta | Sim | "Só quem tem a chave consegue ler isto?" | CPF guardado no Postgres |

O cheat sheet da OWASP é direto sobre uma dessas escolhas: senhas não devem ser protegidas com criptografia reversível. Se um atacante obtém sua chave e sua tabela, todas as senhas saem. Use um algoritmo de hash de senha, e o cheat sheet aponta para o irmão dele, o Password Storage Cheat Sheet, para os detalhes.

O erro oposto é fazer hash de um CPF. Você precisa dele de volta para enviar ao banco parceiro, e um SHA-256 de um número de 11 dígitos é trivial de quebrar por força bruta de qualquer forma. Um CPF precisa de criptografia.

HMAC e assinaturas resolvem outro problema: integridade e origem, não sigilo. O corpo de um webhook não é segredo para quem recebe. O que o receptor precisa saber é que foi você quem enviou e que ninguém alterou. Com HMAC os dois lados têm o mesmo segredo, então você precisa entregar um segredo a cada cliente por um canal seguro. Com uma assinatura, você guarda a chave privada e publica a chave pública. É por isso que o TCM pede um "endpoint público com chaves de verificação": chaves públicas podem ser publicadas, segredos compartilhados não.

## 2. Criptografar dados em repouso, do jeito da OWASP

*Fonte principal: OWASP, "Cryptographic Storage Cheat Sheet", seções "Architectural Design", "Algorithms", "Secure Random Number Generation" e "Defense in Depth".*

**Decida onde criptografar a partir do modelo de ameaças.** O cheat sheet lista quatro camadas: aplicação, banco de dados, sistema de arquivos e hardware. Criptografia de disco protege contra alguém que sai com um disco na mão, mas não faz nada contra um SQL injection, porque o banco descriptografa as páginas para qualquer um que consiga consultá-lo. Se a ameaça é "um atacante lê linhas pela aplicação ou por um backup vazado", você precisa de criptografia das colunas sensíveis na camada de aplicação.

**Guarde menos.** O conselho mais forte do cheat sheet é uma frase só: "The best way to protect sensitive information is to not store it in the first place." Ele usa números de cartão como exemplo. Na terça-feira você vê como a tokenização permite que uma carteira nunca guarde números de cartão.

**Escolha algoritmos chatos e autenticados.** Para criptografia simétrica, o cheat sheet recomenda AES com chave de pelo menos 128 bits, idealmente 256. Ele quer modos autenticados sempre que disponíveis, com GCM e CCM como primeiras opções. CTR e CBC são alternativas que precisam de um MAC separado (Encrypt-then-MAC), e ECB deve ser evitado. Sobre algoritmos próprios, o conselho tem três palavras: "Don't do this."

Um modo autenticado detecta adulteração: se alguém muda bytes de um texto cifrado com AES-GCM, a descriptografia falha. Você também pode vincular **dados adicionais autenticados (AAD)**, como o ID do cliente, para que um texto cifrado copiado da linha de um cliente para a de outro falhe ao descriptografar.

**Use um gerador aleatório criptograficamente seguro** para chaves, IVs e tokens. Em Node.js isso é `crypto.randomBytes()`, nunca `Math.random()`. O cheat sheet também avisa para não confiar em UUIDs como segredos, a menos que você saiba que o gerador é criptograficamente seguro.

Um helper mínimo de AES-256-GCM em Node.js fica assim. O IV de 12 bytes precisa ser único para cada criptografia com a mesma chave, e é por isso que vem de `randomBytes`.

```ts
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';

export function encrypt(plaintext: Buffer, key: Buffer, aad: Buffer) {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  cipher.setAAD(aad);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  return { iv, ciphertext, tag: cipher.getAuthTag() };
}

export function decrypt(c: { iv: Buffer; ciphertext: Buffer; tag: Buffer }, key: Buffer, aad: Buffer) {
  const decipher = createDecipheriv('aes-256-gcm', key, c.iv);
  decipher.setAAD(aad);
  decipher.setAuthTag(c.tag); // final() lança erro se a tag não bater
  return Buffer.concat([decipher.update(c.ciphertext), decipher.final()]);
}
```

O cheat sheet prefere que uma biblioteca cuide dos IVs por você, então em produção use uma biblioteca mantida ou o cliente do seu KMS. O trecho só mostra as peças em movimento.

**Defesa em profundidade.** O cheat sheet diz que aplicações "should be designed to still be secure even if cryptographic controls fail." Criptografia não substitui checagens de autorização, e um ID criptografado em uma URL não é controle de acesso.

## 3. Gestão de chaves: a parte que realmente quebra

*Fonte principal: OWASP, "Cryptographic Storage Cheat Sheet", seções "Key Management" e "Key Storage".*

Um algoritmo é tão forte quanto o sigilo da sua chave. O cheat sheet pede processos formais e testados para todo o ciclo de vida da chave: geração, armazenamento, distribuição, implantação nos servidores, rotação e descomissionamento.

**Geração.** Chaves precisam vir de uma função criptograficamente segura, nunca de palavras, frases ou padrões de teclado. Use chaves independentes para propósitos independentes. A chave que criptografa CPFs não pode também assinar webhooks.

**Rotação.** O cheat sheet lista quando rotacionar:

- Quando se sabe ou se suspeita que a chave foi comprometida, inclusive quando alguém com acesso sai da empresa.
- Quando o criptoperíodo termina (ele cita a NIST SP 800-57 como guia para os períodos).
- Quando a quantidade de dados criptografados com a chave se aproxima do limite seguro do modo.
- Quando a segurança do algoritmo muda, por exemplo depois de um novo ataque.

Depois de rotacionar, os dados existentes podem ser tratados de duas formas. Você pode descriptografar e criptografar tudo de novo com a nova chave, o que o cheat sheet diz que deve ser preferido em geral. Ou pode marcar cada texto cifrado com o ID da chave que o produziu e manter as chaves antigas disponíveis para descriptografar. Na prática, carteiras costumam fazer a segunda coisa imediatamente e a primeira como job em segundo plano. Em qualquer caso, o cheat sheet lembra de manter chaves aposentadas por um tempo, para que backups antigos continuem legíveis.

**Armazenamento.** O cheat sheet recomenda primeiro mecanismos dedicados: HSMs, cofres de chaves como AWS KMS ou Azure Key Vault, e gerenciadores de segredos como HashiCorp Vault. Quando eles não estão disponíveis, as regras básicas são: não deixe chaves fixas no código, não as coloque no controle de versão, restrinja as permissões dos arquivos de configuração que as contêm e evite variáveis de ambiente, que podem vazar por páginas de debug ou por `/proc/self/environ`.

**Separação.** "Where possible, encryption keys should be stored in a separate location from encrypted data." Se a chave fica no mesmo banco que o texto cifrado, um único SQL injection ou um backup roubado entrega as duas metades ao atacante.

## 4. Envelope encryption

*Fontes principais: OWASP, "Cryptographic Storage Cheat Sheet", seção "Encrypting Stored Keys"; AWS KMS Developer Guide, "AWS KMS cryptography essentials", seção "Envelope encryption".*

A separação cria um problema prático. Você não pode chamar um serviço remoto de chaves para cada byte de cada linha, nem manter uma chave mestra na memória da aplicação para sempre. A resposta é uma hierarquia de dois níveis.

A OWASP dá nome aos níveis. A **Data Encryption Key (DEK)** criptografa os dados. A **Key Encryption Key (KEK)** criptografa a DEK. A DEK criptografada pode ficar logo ao lado dos dados, porque sem a KEK ela é inútil. A KEK precisa ser guardada separadamente e ser pelo menos tão forte quanto a DEK.

A AWS define a mesma ideia: "Envelope encryption is the practice of encrypting plaintext data with a data key, and then encrypting the data key under another key." O topo da hierarquia é a **root key**, que na AWS é uma KMS key. O guia lista os benefícios:

- A data key criptografada pode ser guardada junto dos dados criptografados.
- Para criptografar os mesmos dados com várias chaves, você só criptografa de novo a pequena data key, não os dados.
- Você pode combinar algoritmos: criptografia simétrica rápida para os dados e outro esquema para a camada de chaves.

Veja como a criptografia de CPF do TCM se encaixa (quinta-feira, item 3):

1. Na criação do cliente, peça ao KMS (ou ao Vault) uma nova data key. Você a recebe duas vezes: uma em texto claro e outra criptografada com a chave mestra.
2. Criptografe o CPF localmente com a DEK em texto claro usando AES-256-GCM, com o ID do cliente como AAD.
3. Guarde o texto cifrado, o IV, a tag, a DEK criptografada e o ID da chave mestra. Apague a DEK em texto claro da memória.
4. Para ler o CPF, envie a DEK criptografada ao KMS, receba a DEK em texto claro e descriptografe localmente.

```sql
CREATE TABLE customer_pii (
  customer_id     uuid PRIMARY KEY REFERENCES customers(id),
  cpf_ciphertext  bytea NOT NULL,
  cpf_iv          bytea NOT NULL,
  cpf_tag         bytea NOT NULL,
  dek_encrypted   bytea NOT NULL,  -- inútil sem a KEK
  kek_id          text  NOT NULL,  -- qual chave mestra (e versão) embrulhou a DEK
  created_at      timestamptz NOT NULL DEFAULT now()
);
```

Uma DEK por registro custa uma chamada ao KMS por escrita e por leitura sem cache. Em troca, rotacionar a chave mestra só reembrulha DEKs pequenas, e destruir a DEK de um registro o torna ilegível em todo lugar, inclusive nos backups. A seção de LGPD de terça-feira usa essa propriedade.

## 5. KMS, HSM e rotação na prática

*Fontes principais: AWS KMS Developer Guide, "AWS KMS cryptography essentials" e "Rotate AWS KMS keys"; documentação do HashiCorp Vault, "Transit secrets engine".*

Um **hardware security module (HSM)** é um dispositivo resistente a adulteração que gera chaves e as usa internamente, de modo que a chave nunca aparece na memória do seu servidor. Um **KMS** é um serviço gerenciado na frente de HSMs, com API, políticas de acesso e logs de auditoria.

O guia da AWS afirma a garantia central sem rodeios: KMS keys "never leave the AWS KMS FIPS 140-3 Security Level 3 validated hardware security modules unencrypted." Para usar uma chave, você precisa chamar o KMS. Outros fatos do guia que valem a nota:

- Toda criptografia simétrica dentro dos HSMs usa AES-GCM com chaves de 256 bits.
- Para cada criptografia com uma KMS key, o KMS deriva uma chave por chamada com uma KDF em modo contador usando HMAC com SHA-256.
- `GenerateDataKey` devolve uma data key em texto claro mais uma cópia criptografada, exatamente o que envelope encryption precisa.

A página de rotação traz a parte que você precisa para entrevistas. Para KMS keys simétricas com material gerado pelo próprio KMS, existe rotação automática, com período padrão de 365 dias. O KMS mantém todo o material de chave anterior, então textos cifrados antigos continuam descriptografando: na descriptografia, "AWS KMS automatically chooses the correct version." O ID da chave nunca muda, então as aplicações não precisam mudar. A rotação não criptografa de novo seus dados nem suas data keys. Chaves assimétricas e chaves HMAC não podem ser rotacionadas automaticamente. Para elas, você rotaciona manualmente: cria uma chave nova e aponta sua aplicação ou um alias para ela.

Esse último ponto importa para a assinatura de webhooks. Uma chave de assinatura é assimétrica, então "rotação" significa uma chave nova com um ID novo, publicada ao lado da antiga por um tempo.

**Vault Transit, para o lab.** No lab você vai rodar o Vault em modo dev, cujo engine Transit criptografa e descriptografa dados para você sem expor a chave. Os comandos da documentação do Vault:

```bash
vault secrets enable transit
vault write -f transit/keys/wallet-pii
vault write transit/encrypt/wallet-pii plaintext=$(echo "123.456.789-09" | base64)
# -> ciphertext: vault:v1:...
vault write -f transit/keys/wallet-pii/rotate
vault write transit/rewrap/wallet-pii ciphertext=vault:v1:...
# -> ciphertext: vault:v2:...
```

O `v1` no texto cifrado é a versão da chave, a mesma ideia de "marcar cada texto cifrado com o ID da chave" da OWASP. `rewrap` criptografa de novo com a versão mais recente sem nunca devolver o texto claro para você. O Vault também tem a configuração `min_decryption_version`: versões abaixo dela são arquivadas, e é assim que você finalmente aposenta uma versão antiga depois que tudo foi reembrulhado.

## 6. TLS e TLS mútuo

*Fonte principal: Cloudflare Learning, "What is mutual TLS (mTLS)?"*

Até aqui protegemos dados em repouso. Em trânsito, a ferramenta é o TLS. A Cloudflare descreve o TLS como um protocolo que autentica o servidor e criptografa o tráfego para que terceiros não consigam lê-lo. O servidor prova sua identidade com um certificado, que contém sua chave pública, a autoridade certificadora (CA) emissora e uma data de validade, e prova durante o handshake que possui a chave privada correspondente.

No TLS comum, só o servidor é autenticado. O app da sua carteira sabe que está falando com a sua API, mas a sua API não aprende nada sobre o cliente pelo TLS em si. Isso basta para a web pública, onde usuários se autenticam com senhas e tokens.

O **TLS mútuo** faz os dois lados apresentarem um certificado. O artigo da Cloudflare lista os passos: o cliente conecta, o servidor apresenta seu certificado, o cliente o verifica, depois o cliente apresenta o próprio certificado, o servidor o verifica, o servidor concede acesso e o tráfego criptografado começa.

Onde o mTLS entra em uma fintech:

- **Entre seus serviços.** Em uma rede zero trust, o serviço de ledger não deveria aceitar um pedido de posting só porque veio de dentro da VPC. Com mTLS ele aceita apenas chamadores com um certificado emitido para, por exemplo, o serviço de transferências.
- **Com parceiros.** Bancos parceiros e arranjos de pagamento costumam exigir mTLS em suas APIs, e o ecossistema do Pix no Brasil também usa certificados de cliente. A chave privada do seu certificado de cliente vira mais uma chave para guardar em um cofre e rotacionar antes de expirar.

No mTLS, diz a Cloudflare, "The organization implementing mTLS acts as its own certificate authority." Ela emite um certificado raiz, e todo certificado de cliente e de servidor autorizado precisa encadear até ele. O artigo lista ataques que isso dificulta: ataques on-path, spoofing, credential stuffing, força bruta, phishing e requisições de API maliciosas. Sobre atacantes on-path ele é específico: eles "cannot authenticate to either the client or the server."

A Cloudflare explica que o mTLS não é usado na internet inteira porque gerenciar um certificado em cada dispositivo de usuário final é impraticável. Na quarta-feira você vai ver que o BCP de segurança do OAuth também usa mTLS para vincular tokens a um cliente.

## 7. Chaves de assinatura de webhooks: prévia de quinta-feira

*Fontes principais: as seções acima, aplicadas às tarefas do TCM. Esta seção é o design do curso, não uma citação de uma referência específica.*

No Módulo 5, seu emissor de webhooks assinava com HMAC-SHA256, um ID de evento e um timestamp, seguindo a especificação Standard Webhooks. Isso cobria integridade e replay. Não cobria o ciclo de vida da chave: um segredo só, sem ID de chave, sem plano para trocá-lo.

A pergunta de domínio do TCM é: onde vivem as chaves que assinam seus webhooks, e como você as rotaciona sem quebrar os clientes? Tudo o que vimos hoje aponta para uma resposta.

**Onde elas vivem.** A chave privada de assinatura vive no Vault ou no KMS, nunca no repositório ou em uma variável de ambiente, seguindo as regras de armazenamento da OWASP. O ideal é que a operação de assinatura aconteça dentro do serviço de chaves, para que a chave privada nunca chegue à sua aplicação.

**Como os clientes verificam.** Cada webhook leva um header com a assinatura, um timestamp e um `kid` (ID da chave). Assinar o timestamp junto com o corpo permite ao receptor rejeitar replays antigos. O receptor busca suas chaves públicas em um endpoint público, escolhe a que corresponde ao `kid` e verifica.

```ts
import { sign, verify } from 'node:crypto';

// Ed25519: o argumento de algoritmo é null
const message = Buffer.from(`${timestamp}.${rawBody}`);
const signature = sign(null, message, privateKey);            // emissor
const ok = verify(null, message, publicKeysByKid[kid], signature); // receptor
```

**Como rotacionar sem falhas.** A rotação tem três fases, e a ordem importa:

| Fase | Chaves publicadas | Chave que assina | Por quê |
| --- | --- | --- | --- |
| 1. Publicar | antiga + nova | antiga | Clientes que fazem cache das chaves conhecem a nova antes de vê-la em uso |
| 2. Trocar | antiga + nova | nova | Webhooks em trânsito e em retry assinados com a antiga continuam verificando |
| 3. Aposentar | nova | nova | Só depois que a sobreposição for maior que o TTL do cache do cliente mais a sua janela de retry |

Se você troca a chave de assinatura antes de os clientes terem a nova chave pública, algumas verificações falham. Se remove a chave antiga enquanto ainda há retries assinados com ela na fila, esses também falham. A sobreposição é o que torna "zero falhas de verificação" possível.

Com HMAC as mesmas três fases se aplicam, mas cada cliente precisa receber o novo segredo por um canal seguro. Esse passo extra de distribuição é o principal motivo para preferir assinaturas assimétricas em webhooks.

## O que anotar hoje

1. Hash x criptografia x HMAC (e assinaturas): o que cada um responde, se usa chave, se é reversível e um exemplo de cada na carteira.
2. O básico de gestão de chaves: como as chaves são geradas, onde ficam guardadas, por que chaves e dados ficam separados e os quatro motivos para rotacionar.
3. TLS x mTLS: quem autentica quem, e dois lugares na carteira onde você usaria mTLS.
4. KMS x HSM, envelope encryption (DEK e KEK, desenhadas em um diagrama para o CPF) e o que a rotação automática faz e não faz no AWS KMS.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que uma senha nunca deve ser guardada com criptografia reversível, e por que um CPF não pode ser guardado como hash?
- O que um modo autenticado como AES-GCM dá que o CBC sozinho não dá?
- Em envelope encryption, o que a DEK criptografa, o que a KEK criptografa, e qual delas pode ficar ao lado dos dados?
- Quando o AWS KMS rotaciona uma chave simétrica automaticamente, seu texto cifrado antigo precisa ser criptografado de novo? Por que não?
- O que o mTLS acrescenta ao TLS comum, e quem faz o papel de autoridade certificadora?
- Por que a rotação de uma chave de assinatura de webhooks precisa de um período de sobreposição, e o que decide a duração dele?
- Por que uma assinatura assimétrica combina melhor que HMAC com um endpoint público de chaves de verificação?

## Referências

- **Fonte principal:** OWASP Cheat Sheet Series, ["Cryptographic Storage Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html). Leia "Architectural Design", "Algorithms" (modos de cifra e aleatoriedade segura), "Key Management" e "Key Storage" por inteiro. Gratuito.
- Cloudflare Learning, ["What is mutual TLS (mTLS)?"](https://www.cloudflare.com/learning/access-management/what-is-mutual-tls/). Leia a página inteira; ela é curta. Gratuito.
- AWS KMS Developer Guide, ["AWS KMS cryptography essentials"](https://docs.aws.amazon.com/kms/latest/developerguide/kms-cryptography.html). Leia "Envelope encryption", as partes de HSM e derivação de chaves, e passe pela tabela de operações. Gratuito.
- AWS KMS Developer Guide, ["Rotate AWS KMS keys"](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html). A fonte dos fatos sobre rotação da seção 5. Gratuito.
- Documentação do HashiCorp Vault, ["Transit secrets engine"](https://developer.hashicorp.com/vault/docs/secrets/transit). Deixe aberta durante o lab para os comandos de encrypt, decrypt, rotate e rewrap. Gratuito.
