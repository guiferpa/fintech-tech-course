# Roteiro · M8 · Dia 3 · OAuth, BOLA, limites e PLD


## Abertura

Esta é a aula em vídeo do módulo oito, dia três: OAuth, bola, limites e prevenção à lavagem de dinheiro.

Todo pedido para mover dinheiro responde três perguntas antes de tocar o ledger. Quem está chamando? Isso é autenticação, com tokens OAuth e J W Ts. Quem chama pode agir sobre esta conta específica? Autorização por objeto, onde mora o bola. E, mesmo podendo, esta transferência deve passar agora? Isso é risco: limites, velocity checks, e os deveres de prevenção à lavagem de dinheiro. Erre nas duas primeiras, e um atacante move o dinheiro dos outros. Erre na terceira, e uma conta legítima vira laranja, ou a sua checagem antifraude cai e leva todas as transferências junto.


## RFC 9700

A R F C 9700, de 2025, reúne uma década de ataques a OAuth e os transforma em regras. As que um time de carteira deveria saber de cor.

A redirect URI é comparada por igualdade exata de texto. Curingas deixam um atacante registrar uma URI que captura códigos.

Clientes públicos usam pixie, com o método S 256. Ele impede a injeção de authorization code.

Nada de implicit grant, que vaza tokens por URLs e histórico do navegador. E nada de password grant, em que o app vê a senha do usuário e não combina com autenticação multifator.

Access tokens vinculados ao cliente, com M T L S ou D pop. Um token roubado fica inútil sem a chave privada do cliente.

Refresh tokens de clientes públicos vinculados, ou rotacionados a cada uso. Senão um refresh vazado funciona por meses.

E menor privilégio, com audiência restrita. Um token do serviço de extrato não pode ser reutilizado no de transferências.

A R F C também amplia o modelo de atacante: ele pode rodar o próprio servidor de autorização, ler respostas vazadas em logs, e obter tokens vazados. Num mundo onde tokens vazam, um bearer token é um cheque ao portador. Por isso APIs como as do Open Finance combinam OAuth com M T L S.

> **Pausa:** Pergunta: por que um token vinculado ao remetente é melhor que um bearer token?

Porque o bearer token funciona para quem o tiver. O vinculado exige também a chave privada do cliente, então um token vazado sozinho não serve.


## Armadilhas de JWT

A maioria das carteiras usa J W Ts como access tokens. Fácil de emitir, e fácil de verificar mal. As armadilhas do cheat sheet da O wasp.

Alg none: algumas bibliotecas já aceitaram tokens sem assinatura. Garanta que o seu parser não aceite.

Confusão de algoritmo: se o header do token escolhe o algoritmo, o atacante faz o verificador tratar a sua chave pública R S A como segredo H mac. Como a chave é pública, ele forja tokens. Fixe no código os algoritmos aceitos.

Chaves indicadas no header, como J K U ou J W K, podem apontar para uma chave do atacante. Pegue as chaves do J W K S U R I configurado do emissor, nunca do token.

Sempre valide emissor e audiência, e nunca verifique contra a união das chaves de vários emissores. E cheque o tipo: um token de redefinição de senha não pode valer como access token.

Um J W T vale até expirar. Mantenha expirações curtas, e se precisar revogar, use uma denylist pelo J T I e o emissor, não pela string do token.

E o payload é codificado, não criptografado. Nunca ponha CPF, saldo ou cartão nas claims. No Nest J S, quase tudo isso é passar as opções certas ao verify: algoritmos fixos, emissor e audiência. E o K I D permite rotacionar as chaves de assinatura, como nos webhooks.

> **Pausa:** Pergunta: como funciona o ataque de confusão de algoritmo?

O atacante troca o alg do header para H mac e assina com a sua chave pública como segredo. Se o verificador obedece o header, aceita. Por isso a lista de algoritmos é fixa.


## BOLA

A autenticação diz que quem chama é o cliente quarenta e dois. Ela não diz se o cliente quarenta e dois pode ler a conta nove um três sete. O bola é fácil de explorar: o atacante troca um I D e vê se a resposta muda. Na carteira: o extrato de qualquer pessoa, uma transferência com a conta de origem de outro, ou apagar a chave Pix salva de outro cliente.

O padrão mais robusto é fazer a posse parte da query. Ligue os lançamentos à conta, e filtre pela conta e pelo dono. Se vier vazio e a conta não for sua, responda 404, não 403, para não confirmar que ela existe.

Comparar o I D do usuário do J W T com o parâmetro cobre só uma parte dos casos. A posse costuma ser indireta: a transferência pertence a uma conta, que pertence a um cliente, ou a uma empresa onde o usuário tem um papel.

Com a posse na query, uma checagem esquecida não devolve nada, em vez de devolver os dados de outra pessoa.

E U U I Ds aleatórios dificultam adivinhar, mas não são autorização. I Ds vazam por URLs, logs e prints. Ponha no C I um teste que chama todos os endpoints com I Ds de outro usuário.

> **Pausa:** Pergunta: os I Ds são U U I Ds aleatórios. Ainda preciso checar a posse?

Precisa. I Ds vazam por URLs, logs e prints. Ser difícil de adivinhar não é autorização.


## Regras de risco

Mesmo autenticada e autorizada, uma transferência pode ser fraude: um celular roubado, um cliente vítima de golpe, uma conta usada como laranja. O Radar da Stripe é um bom modelo de regras de risco.

As regras podem pedir 3 D secure, permitir, bloquear, ou mandar para revisão.

E há precedência. As de 3 D secure rodam antes. Review vem depois de block. E allow se sobrepõe a todas, inclusive às regras padrão, então use pouco, e acrescente que o risco não seja o mais alto.

Os atributos de velocidade são contadores por janela: cartões por I P por hora, recusas por cartão por dia, cobranças por e-mail por semana. Eles pegam os sinais clássicos: muitos cartões de um I P, muitas recusas, uma rajada súbita.

Para operar com segurança: na dúvida, revisão em vez de bloqueio, olhe os falsos positivos, e depois decida. Teste a regra contra o histórico antes de ativar.

Faça o rollout aos poucos. Em zero por cento, a regra roda em modo shadow, e só informa o que teria feito. E mantenha trilha de auditoria das mudanças.


## Serviço de limites

Na sexta você constrói o serviço de limites. Um conjunto inicial de regras.

Por transferência: acima de cinco mil reais, bloqueie ou exija autenticação reforçada.

Diário acumulado: a soma de hoje mais o valor acima de dez mil, bloqueie.

Noturno: das vinte às seis horas, acima de mil reais. Bancos brasileiros aplicam limite noturno ao Pix.

Velocidade: mais de cinco transferências em dez minutos vai para revisão. Uma consulta simples numa tabela indexada basta, contando e somando as transferências recentes da conta.

Favorecido novo: a primeira transferência para uma chave, acima de quinhentos reais, fica retida para revisão.

E o serviço de limites está no caminho do dinheiro, então um timeout significa não sei. Decida antes. Para valores altos, fail closed: retenha, porque deixar passar uma fraude custa mais que atrasar. Para valores pequenos, fail open com um limite local conservador, para uma queda não parar todo Pix de vinte reais. E sempre registre que foi fallback, para checar de novo quando o serviço voltar.

> **Pausa:** Pergunta: o serviço de limites deu timeout numa transferência de oito mil reais. O que acontece?

Fail closed: a transferência fica retida, com o motivo registrado como fallback, e é checada de novo quando o serviço voltar.


## PLD: Circular 3.978

Regras de velocidade protegem seus clientes de fraudadores. Regras de prevenção à lavagem de dinheiro protegem o sistema financeiro dos seus clientes. No Brasil, instituições de pagamento seguem a Circular três mil novecentos e setenta e oito, de 2020. Passe pela estrutura.

Avaliação interna de risco: produtos, clientes e canais classificados por risco, revisada a cada dois anos.

Conhecer o cliente, K Y C, são três passos, não um. Identificação: quem é, com dados verificados. Qualificação: onde mora, capacidade financeira, mantidas atualizadas. E classificação de risco, que deveria mudar os limites do cliente.

Registro de toda operação, com origem e destino dos recursos.

Monitoramento: operações suspeitas selecionadas em até quarenta e cinco dias e analisadas em até mais quarenta e cinco, cada uma num dossiê documentado.

Comunicação ao Coaf até o dia útil seguinte à decisão de comunicar.

E guarda por pelo menos dez anos. É a obrigação legal por trás da resposta de LGPD de ontem.

Pessoas expostas politicamente têm procedimentos reforçados, e a condição dura cinco anos depois de deixarem o cargo. Isso é um campo no modelo de cliente. E as comunicações ao Coaf são feitas sem dar ciência ao envolvido: o app nunca mostra comunicado ao Coaf.

> **Pausa:** Pergunta: quais são os três passos do K Y C?

Identificação, qualificação e classificação de risco.


## Preparação do projeto

O critério do projeto é concreto: rotacionar a chave de assinatura com um cliente de webhook ativo causa zero falhas. Você precisa de um cliente que prove isso.

Ele busca as suas chaves públicas no endpoint, e guarda em cache com T T L.

Diante de um K I D desconhecido, busca de novo uma vez antes de falhar, para pegar rápido uma chave recém-publicada.

Verifica assinatura e timestamp em todo webhook, e conta sucessos e falhas num endpoint que o teste lê.

E roda sob carga constante, uma transferência a cada duzentos milissegundos, enquanto você rotaciona.

Depois, escreva a lista de tarefas de quinta e sexta: assinatura com K I D e duas chaves, o script de rotação, o envelope do CPF, a redação de logs, o serviço de limites com fallback, e o documento com stride, inventário de chaves e retenção da LGPD.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: por que nunca deixar o header do J W T escolher o algoritmo?

Por causa da confusão de algoritmo: o atacante usa a sua chave pública como segredo H mac e forja tokens.

> **Pausa:** Pergunta dois: por que responder 404, e não 403, quando alguém pede a conta de outro?

Para não confirmar que a conta existe.

> **Pausa:** Pergunta três: qual o prazo para comunicar um caso suspeito ao Coaf?

Até o dia útil seguinte ao da decisão de comunicar, sem dar ciência ao cliente.


## O que anotar e próximo passo

Anote com as suas palavras: os ataques a OAuth e as defesas. As armadilhas de J W T. O seu padrão de posse na query. A tabela de limites com o fallback. E a estrutura da circular de prevenção à lavagem.

Depois, desenhe o cliente de webhook de teste e escreva a lista de tarefas do projeto. Até a próxima aula.
