[English](DSA.md)

# Trilha de DSA

Muitas fintechs, e quase toda empresa que contrata para fora, têm uma etapa de coding (estruturas de dados e algoritmos) antes do system design. Esta trilha prepara você para ela sem tirar tempo dos dias de conclusão: **os primeiros 30 minutos de toda sessão de segunda a quarta** (por exemplo, das 19:00 às 19:30, com a sessão terminando às 22:30). Quinta e sexta continuam 100% de conclusão.

Em 13 semanas você resolve os problemas clássicos de entrevista, agrupados por padrão, dos de aquecimento (Two Sum, Top K) aos difíceis (LFU Cache, Median from Data Stream, Word Break). As semanas de checkpoint e a semana final usam o horário para refazer problemas e para simulados de coding gravados.

## Regras

- **Sem IA**, como nos dias de conclusão. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA.
- **Limite de 30 minutos.** Se travar depois de 20 minutos, leia só a abordagem no editorial do LeetCode (não o código), feche, codifique você mesmo e marque o problema como **refazer**.
- **Use a linguagem da entrevista.** TypeScript mantém a consistência com o curso; Python também é comum em entrevistas.
- **Guarde as soluções** numa pasta `dsa/` do seu repositório de prática, um arquivo por problema com a complexidade num comentário.

## Método para cada problema (em voz alta, como na entrevista)

1. Reformule o problema e pergunte sobre casos de borda (entrada vazia, duplicados, negativos, limites de tamanho).
2. Resolva um exemplo pequeno à mão.
3. Diga a força bruta e a complexidade dela.
4. Encontre o padrão (a tabela abaixo diz qual) e a complexidade melhor.
5. Codifique e teste à mão com o exemplo e um caso de borda.
6. Diga a complexidade final de tempo e espaço.

## Flashcards

Para cada problema, crie um card com o **truque** (não o código): "Subarray sum equals K: qual estrutura e por que funciona com negativos?". Use a tag `dsa`. Nos checkpoints, revise a tag `dsa`. Veja o [guia de flashcards](FLASHCARDS.pt-BR.md).

## Cronograma

| Semana | Dia | Problema | Padrão |
| --- | --- | --- | --- |
| 1 (M1) | Seg | [Two Sum](https://leetcode.com/problems/two-sum/)<br>[Two Sum II](https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/) | hash map<br>two pointers em array ordenado |
| 1 (M1) | Ter | [3Sum](https://leetcode.com/problems/3sum/) | ordenação + two pointers, generaliza para k-sum |
| 1 (M1) | Qua | [Top K Frequent Elements](https://leetcode.com/problems/top-k-frequent-elements/) | heap, depois bucket sort em O(n) |
| 2 (M2) | Seg | [Kth Largest Element in a Stream](https://leetcode.com/problems/kth-largest-element-in-a-stream/) | min-heap de tamanho k |
| 2 (M2) | Ter | [Maximum Subarray](https://leetcode.com/problems/maximum-subarray/)<br>[Maximum Product Subarray](https://leetcode.com/problems/maximum-product-subarray/) | Kadane<br>variação de Kadane (guarda mínimo e máximo) |
| 2 (M2) | Qua | [Longest Substring Without Repeating Characters](https://leetcode.com/problems/longest-substring-without-repeating-characters/) | sliding window |
| 3 (M3) | Seg | [Subarray Sum Equals K](https://leetcode.com/problems/subarray-sum-equals-k/) | prefix sum + hash map |
| 3 (M3) | Ter | [Merge Intervals](https://leetcode.com/problems/merge-intervals/) | intervalos: ordenar pelo início |
| 3 (M3) | Qua | [Koko Eating Bananas](https://leetcode.com/problems/koko-eating-bananas/) | busca binária na resposta |
| 4 (M4) | Seg | [Capacity To Ship Packages Within D Days](https://leetcode.com/problems/capacity-to-ship-packages-within-d-days/) | busca binária na resposta (capacidade, dias, pesos) |
| 4 (M4) | Ter | [Clone Graph](https://leetcode.com/problems/clone-graph/) | DFS/BFS em grafo + hash map de cópias |
| 4 (M4) | Qua | [Copy List with Random Pointer](https://leetcode.com/problems/copy-list-with-random-pointer/) | hash map, depois intercalação com espaço O(1) |
| 5 (C1) | Seg | Refaça do zero 2 problemas que você marcou como "refazer" nas semanas 1 a 4, sem dicas. | — |
| 5 (C1) | Ter | Simulado de entrevista de coding (30 min, gravado): sorteie um problema das semanas 1 a 4 e resolva explicando em voz alta, como numa entrevista. | — |
| 5 (C1) | Qua | Revisão de complexidade: escreva de memória a complexidade de tempo e espaço de cada problema até aqui, confira e transforme os erros em flashcards. | — |
| 6 (M5) | Seg | [Course Schedule](https://leetcode.com/problems/course-schedule/)<br><sub>Mesma ideia da detecção de deadlock num wait-for graph.</sub> | detecção de ciclo em grafo dirigido (DFS com 3 cores) |
| 6 (M5) | Ter | [Course Schedule II](https://leetcode.com/problems/course-schedule-ii/) | ordenação topológica (Kahn) |
| 6 (M5) | Qua | [Accounts Merge](https://leetcode.com/problems/accounts-merge/) | union-find |
| 7 (M6) | Seg | [Word Ladder](https://leetcode.com/problems/word-ladder/) | BFS para menor caminho |
| 7 (M6) | Ter | [Word Ladder (optimization)](https://leetcode.com/problems/word-ladder/)<br><sub>Refaça a solução de ontem, agora com BFS bidirecional, e compare os tempos.</sub> | BFS bidirecional + mapa de curingas |
| 7 (M6) | Qua | [Merge K Sorted Lists](https://leetcode.com/problems/merge-k-sorted-lists/)<br><sub>Mesmo formato de juntar streams ordenados de eventos numa reconciliação.</sub> | min-heap, ou dividir e conquistar |
| 8 (M7) | Seg | Rate limiter: token bucket<br><sub>Sem link do LeetCode: escreva uma classe com allow(userId, now) e testes unitários de rajada e reposição.</sub> | design + código: allow(userId, now) |
| 8 (M7) | Ter | Rate limiter: sliding window<br><sub>Mesma interface de ontem; compare memória e precisão nas bordas da janela.</sub> | sliding window log, depois sliding window counter |
| 8 (M7) | Qua | [Trapping Rain Water](https://leetcode.com/problems/trapping-rain-water/) | two pointers, depois pilha monotônica |
| 9 (C2) | Seg | Refaça do zero 2 problemas que você marcou como "refazer" nas semanas 6 a 8, sem dicas. | — |
| 9 (C2) | Ter | Simulado de entrevista de coding (30 min, gravado): sorteie um problema das semanas 6 a 8 e resolva explicando em voz alta, como numa entrevista. | — |
| 9 (C2) | Qua | Revisão de complexidade: escreva de memória a complexidade de tempo e espaço de cada problema até aqui, confira e transforme os erros em flashcards. | — |
| 10 (M8) | Seg | [LRU Cache](https://leetcode.com/problems/lru-cache/) | hash map + lista duplamente ligada |
| 10 (M8) | Ter | [LFU Cache (1/2)](https://leetcode.com/problems/lfu-cache/)<br><sub>Desenhe as estruturas e faça get/put funcionarem.</sub> | hash map + buckets de frequência |
| 10 (M8) | Qua | [LFU Cache (2/2)](https://leetcode.com/problems/lfu-cache/)<br><sub>Termine e teste empates na remoção (mesma frequência, sai o usado há mais tempo).</sub> | hash map + buckets de frequência |
| 11 (M9) | Seg | [Find Median from Data Stream](https://leetcode.com/problems/find-median-from-data-stream/) | dois heaps |
| 11 (M9) | Ter | [Task Scheduler](https://leetcode.com/problems/task-scheduler/) | guloso + max-heap |
| 11 (M9) | Qua | Priority scheduler<br><sub>Sem link do LeetCode: schedule(task, priority, runAt) e next(now), mais retry com backoff exponencial para tarefas que falham.</sub> | design + código: heap ordenado por (runAt, prioridade) |
| 12 (M10) | Seg | [Longest Increasing Subsequence](https://leetcode.com/problems/longest-increasing-subsequence/) | DP O(n²), depois patience sorting em O(n log n) |
| 12 (M10) | Ter | [Serialize and Deserialize Binary Tree](https://leetcode.com/problems/serialize-and-deserialize-binary-tree/) | DFS em pré-ordem com marcadores de nulo |
| 12 (M10) | Qua | [Word Break](https://leetcode.com/problems/word-break/) | DP, depois trie para acelerar os prefixos |
| 13 (F) | Seg | Simulado de coding 1 (30 min, gravado): um problema medium sorteado da lista inteira. | — |
| 13 (F) | Ter | Simulado de coding 2 (30 min, gravado): um problema hard sorteado da lista inteira. | — |
| 13 (F) | Qua | Revisão final: refaça o que ainda estiver como "refazer" e atualize sua cola de padrões. | — |

Dois problemas entraram além das listas clássicas porque caem muito em entrevistas de fintech: o **rate limiter** (semana 8) e o **scheduler com prioridade e retries** (semana 11). Eles não têm link do LeetCode: escreva uma classe pequena com testes unitários.
