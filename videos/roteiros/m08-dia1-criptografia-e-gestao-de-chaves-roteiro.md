# Roteiro · M8 · Dia 1 · Criptografia e gestão de chaves


## Abertura

Esta é a aula em vídeo do módulo oito, dia um: criptografia e gestão de chaves.

Uma carteira guarda coisas que machucam quando vazam: CPFs, telefones, credenciais do banco parceiro, as chaves que assinam os webhooks. Mas a maioria dos incidentes não vem de algoritmo quebrado. Vem da ferramenta errada, como criptografar uma senha ou fazer hash de um CPF que você precisa ler de volta. De chaves guardadas ao lado dos dados. E de chaves que ninguém sabe rotacionar. O projeto de quinta pede rotacionar uma chave de assinatura com cliente ativo e zero falhas. Então o ciclo de vida da chave é a parte a dominar.


## Quatro ferramentas

Comece perguntando o que quem lê o dado precisa fazer com ele. Essa pergunta escolhe a ferramenta.

Hash, como sha 256: sem chave, irreversível. Responde se são os mesmos bytes de antes. Exemplo: a impressão digital de um documento.

Hash de senha, como Argon2id ou bcrypt: com salt e lento de propósito. Responde se o usuário digitou a senha certa.

H mac: um segredo compartilhado. Responde se alguém com o segredo produziu isto, sem alteração. Webhook com segredo compartilhado.

Assinatura digital, como E D 25519: a chave privada assina, a pública verifica. Responde se quem tem a chave privada produziu isto.

E criptografia, como A E S G C M: com chave secreta, e reversível. Responde se só quem tem a chave lê. É o caso do CPF no Postgres.

Dois erros clássicos. Senha nunca é criptografada de forma reversível: se o atacante pega a chave e a tabela, todas saem. E CPF nunca vira hash: você precisa dele de volta para o banco parceiro, e um hash de onze dígitos se quebra por força bruta. H mac e assinatura resolvem outro problema: integridade e origem, não sigilo. Com assinatura, você publica a chave pública. Com H mac, precisa entregar um segredo a cada cliente.

> **Pausa:** Pergunta: por que o CPF precisa de criptografia, e não de hash?

Porque você precisa ler o CPF de volta para enviar ao banco parceiro. E um hash de um número de onze dígitos é trivial de quebrar por força bruta.


## Criptografia em repouso

Agora, criptografar dados em repouso, segundo o cheat sheet da O wasp.

Decida a camada pelo modelo de ameaças. Criptografia de disco protege contra quem sai com o disco na mão, mas não contra um SQL injection, porque o banco descriptografa para quem consulta. Contra vazamento pela aplicação ou por backup, criptografe as colunas sensíveis na aplicação.

Guarde menos. A melhor proteção é não guardar a informação. Amanhã você vê como a tokenização evita guardar números de cartão.

Escolha algoritmos chatos e autenticados: A E S com chave de duzentos e cinquenta e seis bits, em modo G C M ou C C M. E C B, nunca. E algoritmo próprio: não faça.

Um modo autenticado detecta adulteração. E você pode vincular dados adicionais autenticados, como o I D do cliente. Aí um texto cifrado copiado da linha de um cliente para a de outro falha ao descriptografar.

Use um gerador aleatório seguro para chaves e I Vs: crypto random bytes no node J S, nunca math random. O I V de doze bytes precisa ser único para cada criptografia com a mesma chave. Em produção, prefira uma biblioteca mantida ou o cliente do K M S.

E defesa em profundidade: um I D criptografado numa URL não é controle de acesso.


## Gestão de chaves

Um algoritmo é tão forte quanto o sigilo da chave. O ciclo de vida inteiro precisa de processo: geração, armazenamento, distribuição, rotação e descomissionamento.

Geração: de uma função segura, nunca de frases. E chaves independentes para propósitos independentes. A chave que criptografa CPFs não assina webhooks.

Rotação: quando a chave foi ou pode ter sido comprometida, inclusive quando alguém com acesso sai da empresa. Quando o criptoperíodo termina. Quando o volume de dados se aproxima do limite seguro. Ou quando o algoritmo enfraquece. Depois, ou você criptografa tudo de novo, ou marca cada texto com o I D da chave e mantém as antigas para ler. Na prática, a segunda na hora e a primeira em segundo plano. E guarde as chaves aposentadas enquanto houver backups.

Armazenamento: primeiro, mecanismos dedicados, como H S M, K M S ou Vault. Nunca no código, no controle de versão, ou em variáveis de ambiente, que vazam por páginas de debug.

E separação: a chave fica longe dos dados. Se ela mora no mesmo banco que o texto cifrado, um SQL injection ou um backup roubado entrega as duas metades.


## Envelope encryption

A separação cria um problema: você não chama um serviço remoto para cada byte, nem mantém uma chave mestra na memória para sempre. A resposta é uma hierarquia de dois níveis. A data encryption key, a D E K, criptografa os dados. A key encryption key, a K E K, criptografa a D E K. Veja o fluxo do CPF no projeto.

Na criação do cliente, peça ao K M S uma nova D E K. Você a recebe duas vezes: em texto claro, e criptografada pela chave mestra.

Criptografe o CPF localmente com a D E K em texto claro, em A E S G C M, com o I D do cliente como A A D.

Grave o texto cifrado, o I V, a tag, a D E K criptografada, e o I D da chave mestra.

E apague a D E K em texto claro da memória. Para ler, mande a D E K criptografada ao K M S, receba a clara, e descriptografe localmente.

A D E K criptografada pode morar ao lado dos dados, porque sem a K E K ela é inútil.

Rotacionar a chave mestra só reembrulha as D E Ks pequenas, não os dados.

E destruir a D E K de um registro o torna ilegível em todo lugar, inclusive nos backups. A aula de LGPD de amanhã usa essa propriedade.

> **Pausa:** Pergunta: por que a D E K criptografada pode ficar na mesma tabela que o CPF criptografado?

Porque, sem a K E K, que fica no K M S, ela é inútil. Um dump do banco não traz a chave mestra.


## KMS e rotação

Um H S M é um dispositivo resistente a adulteração que gera e usa chaves internamente.

A chave nunca aparece na memória do seu servidor. Um K M S é um serviço gerenciado na frente de H S Ms, com API, políticas de acesso e logs de auditoria. No A W S K M S, as chaves nunca saem dos H S Ms sem criptografia. Para usar uma chave, você chama o K M S.

A chamada generate data key devolve uma chave em texto claro e uma cópia criptografada, exatamente o que o envelope precisa.

A rotação automática, para chaves simétricas, roda a cada trezentos e sessenta e cinco dias por padrão. O I D da chave não muda, e o K M S guarda as versões antigas e escolhe a certa ao descriptografar. A aplicação não muda nada.

Mas a rotação não criptografa de novo os seus dados nem as data keys. E chaves assimétricas e H mac não rotacionam automaticamente: você cria uma chave nova, com I D novo. Isso importa para webhooks: uma chave de assinatura é assimétrica, então rotacionar significa publicar uma chave nova ao lado da antiga por um tempo. No lab, você usa o Vault Transit: o texto cifrado traz a versão da chave, v1, v2, e o rewrap recriptografa sem devolver o texto claro.

> **Pausa:** Pergunta: depois da rotação automática no K M S, um texto cifrado antigo ainda abre?

Abre. O K M S guarda todas as versões e escolhe a certa. A rotação só muda a chave usada nas novas criptografias.


## TLS e mTLS

Em trânsito, a ferramenta é o T L S.

No T L S comum, só o servidor é autenticado. Ele prova a identidade com um certificado, que tem a chave pública, a autoridade emissora e a validade, e prova no handshake que tem a chave privada. O app sabe que fala com a sua API, mas a API não aprende nada sobre o cliente. Na web pública, isso basta, porque os usuários fazem login.

No T L S mútuo, os dois lados apresentam certificado, e a organização atua como a própria autoridade certificadora. Onde entra numa fintech: entre seus serviços, numa rede zero trust, o ledger só aceita postings de quem tem um certificado do serviço de transferências, não de qualquer um dentro da V P C. E com parceiros: bancos e o ecossistema Pix usam certificados de cliente. A chave privada desse certificado é mais uma chave a guardar no cofre e rotacionar antes de expirar. Um atacante no meio do caminho não consegue se autenticar a nenhum dos lados.


## Chaves de webhooks

Agora a pergunta do projeto: onde vivem as chaves que assinam seus webhooks, e como rotacioná-las sem quebrar os clientes? A chave privada vive no Vault ou no K M S, e o ideal é assinar dentro do serviço de chaves. Cada webhook leva a assinatura, um timestamp, e o K I D, o I D da chave. O receptor busca as chaves públicas num endpoint, escolhe pelo K I D, e verifica. A rotação tem três fases, e a ordem importa.

Fase um, publicar: as duas chaves públicas no endpoint, mas ainda assinando com a antiga. Clientes com cache conhecem a nova antes de vê-la em uso.

Fase dois, trocar: passe a assinar com a nova. Webhooks em retry, assinados com a antiga, continuam verificando.

Fase três, aposentar: remova a antiga, mas só depois que a sobreposição passar do T T L do cache do cliente mais a sua janela de retry.

Trocar antes de os clientes terem a chave pública nova faz verificações falharem. Remover a antiga com retries na fila também. A sobreposição é o que torna zero falhas possível. Com H mac, as mesmas fases valem, mas cada cliente precisa receber o segredo novo por um canal seguro. Esse passo extra é o principal motivo para preferir assinaturas assimétricas.

> **Pausa:** Pergunta: por que não trocar a chave de assinatura no mesmo instante em que publica a nova?

Porque clientes com a lista de chaves em cache ainda não conhecem a nova, e as verificações falhariam. Primeiro publique, espere o cache expirar, e só então troque.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: para assinar webhooks, H mac ou assinatura digital, e por quê?

Assinatura, porque você publica a chave pública num endpoint, sem precisar entregar um segredo a cada cliente.

> **Pausa:** Pergunta dois: o que é envelope encryption?

Uma data key criptografa os dados, e uma chave mestra, que fica no K M S, criptografa a data key. A data key criptografada mora ao lado dos dados.

> **Pausa:** Pergunta três: a rotação automática do K M S recriptografa os dados existentes?

Não. Ela só muda a versão usada nas novas criptografias, e mantém as antigas para descriptografar.


## O que anotar e próximo passo

Anote com as suas palavras: as cinco ferramentas, com um exemplo de cada. O básico da gestão de chaves. T L S e T L S mútuo. E o envelope encryption do CPF, desenhado.

Depois, no lab, rode o Vault em modo dev com o engine Transit: criptografe, rotacione, faça rewrap, e aposente a versão antiga. Até a próxima aula.
