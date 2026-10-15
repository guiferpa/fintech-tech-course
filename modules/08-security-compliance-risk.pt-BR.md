# Módulo 8: Segurança, compliance e risco

**Semana 10** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](08-security-compliance-risk.md)

## Objetivo

Aplicar segurança onde o dinheiro passa: gestão e rotação de chaves, envelope encryption, escopo de PCI/LGPD, limites e antifraude.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [LRU Cache](https://leetcode.com/problems/lru-cache/) (hash map + lista duplamente ligada) | [OWASP, "Cryptographic Storage Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html) (gratuito): hash x criptografia x HMAC, e o básico de gestão de chaves.<br>[Cloudflare Learning, "What is mutual TLS (mTLS)?"](https://www.cloudflare.com/learning/access-management/what-is-mutual-tls/) (gratuito): TLS e mTLS entre serviços e com parceiros.<br>[AWS KMS Developer Guide, "AWS KMS cryptography essentials"](https://docs.aws.amazon.com/kms/latest/developerguide/kms-cryptography.html) (gratuito): KMS x HSM, envelope encryption e rotação de chaves. | Vault em modo dev (ou LocalStack KMS) no Compose; criptografar e descriptografar pela CLI. |
| Ter | [LFU Cache (1/2)](https://leetcode.com/problems/lfu-cache/) (hash map + buckets de frequência)<br>Desenhe as estruturas e faça get/put funcionarem. | [OWASP API Security Top 10 (2023)](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) (gratuito): os 10 riscos, com BOLA em primeiro.<br>[PCI Security Standards Council, biblioteca de documentos: "PCI DSS Quick Reference Guide"](https://www.pcisecuritystandards.org/document_library/) (gratuito, com cadastro): o que o PCI DSS exige e como a tokenização reduz o escopo.<br>[LGPD, Lei nº 13.709/2018, artigos 7, 16 e 18](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm) (gratuito): pedido de exclusão x dever de guardar registros financeiros. | Threat model STRIDE: diagrama de fluxo de dados do sistema e lista de ameaças (rascunho do docs/m08.md). |
| Qua | [LFU Cache (2/2)](https://leetcode.com/problems/lfu-cache/) (hash map + buckets de frequência)<br>Termine e teste empates na remoção (mesma frequência, sai o usado há mais tempo). | [RFC 9700, "Best Current Practice for OAuth 2.0 Security"](https://www.rfc-editor.org/rfc/rfc9700) (gratuito): os ataques descritos e as defesas recomendadas.<br>[OWASP, "JSON Web Token Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html) (gratuito): armadilhas comuns de JWT.<br>[OWASP, "API1:2023 Broken Object Level Authorization"](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/) (gratuito): autorização por recurso.<br>[Documentação da Stripe, "Fraud prevention rules"](https://docs.stripe.com/radar/rules) (gratuito): limites e velocity checks na prática.<br>[Banco Central do Brasil, Circular nº 3.978/2020](https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50905/Circ_3978_v3_P.pdf) (gratuito): deveres de KYC e prevenção à lavagem de dinheiro; passe pela estrutura. | Preparação do dia de conclusão: cliente de webhook de teste e lista de tarefas. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (1 h) Assinatura de webhook com kid e duas chaves ativas; endpoint público com as chaves de verificação.
2. (1 h) Rotação: nova chave, sobreposição, aposentar a antiga; teste com cliente ativo sem falha de verificação.
3. (1 h) Envelope encryption do CPF: chave de dados por registro, chave mestra no Vault/KMS.
4. (30 min) Redação de CPF, cartão e tokens nos logs.
5. (1 h) Serviço de limites e velocity check com timeout e fallback definido.
6. (30 min) docs/m08.md final.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Rotacionar a chave de assinatura com um cliente de webhook ativo não gera nenhuma falha de verificação.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Onde ficam as chaves que assinam os webhooks que você envia, e como você as rotaciona sem derrubar os clientes?
