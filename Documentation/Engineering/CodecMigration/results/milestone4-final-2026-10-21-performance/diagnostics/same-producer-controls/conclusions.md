# Fixed short-mode same-producer controls

Each control uses the identical binary for both reference/candidate labels. Six cases,16 balanced process pairs per case,5 warmups/5 observations,192 processes each;384 total. Both schedules were frozen before execution. No cross-producer repetition, dropping or automatic waiver.

|Control/case|Encode|Decode|Prepare|Prepare+encode|
|---|---:|---:|---:|---:|
|candidate-self/p12-flat|1.0075|0.9987|1.0260|0.9971|
|candidate-self/p12-ramp|1.0049|1.0185|1.0526|1.0169|
|candidate-self/p12-noise|1.0043|1.0691|1.0064|1.0153|
|candidate-self/p16-flat|1.0055|1.0273|1.0000|0.9875|
|candidate-self/p16-ramp|0.9809|0.9867|0.9873|0.9976|
|candidate-self/p16-noise|1.0026|0.9952|0.9876|1.0016|
|pinned-self/p12-flat|0.9687|0.9879|0.9880|1.0058|
|pinned-self/p12-ramp|0.9686|0.9730|1.0000|0.9962|
|pinned-self/p12-noise|0.9800|0.9569|0.9800|0.9776|
|pinned-self/p16-flat|0.9713|0.9973|1.0000|0.9802|
|pinned-self/p16-ramp|1.0039|0.9964|1.0133|1.0030|
|pinned-self/p16-noise|0.9907|0.9107|1.0000|0.9858|

|Control/case|Operation|Median pair|Block range|IQR|Reference-first|Candidate-first|
|---|---|---:|---|---|---:|---:|
|candidate-self/p12-flat|encode|0.9888|0.7969–1.4317|0.8985–1.0972|0.9888|0.9662|
|candidate-self/p12-flat|decode|0.9988|0.8708–1.1022|0.9620–1.0205|0.9851|1.0052|
|candidate-self/p12-flat|prepare|1.0260|0.9059–1.1370|0.9449–1.0847|1.0392|1.0068|
|candidate-self/p12-flat|prepare_encode|1.0124|0.8850–1.1073|0.9453–1.0556|1.0381|0.9914|
|candidate-self/p12-ramp|encode|1.0089|0.8536–1.2683|0.9723–1.0405|0.9795|1.0183|
|candidate-self/p12-ramp|decode|1.0352|0.8433–1.2236|0.9583–1.0867|1.0504|1.0184|
|candidate-self/p12-ramp|prepare|1.0383|0.9011–1.2375|0.9970–1.0674|1.0465|1.0311|
|candidate-self/p12-ramp|prepare_encode|1.0051|0.9219–1.1400|0.9833–1.0632|0.9906|1.0340|
|candidate-self/p12-noise|encode|0.9956|0.8451–1.2487|0.9499–1.0677|1.0253|0.9846|
|candidate-self/p12-noise|decode|1.0951|0.6660–1.4351|0.9408–1.2225|0.9592|1.2152|
|candidate-self/p12-noise|prepare|1.0126|0.8353–1.2055|0.9446–1.0400|0.9425|1.0360|
|candidate-self/p12-noise|prepare_encode|1.0178|0.9239–1.2333|0.9844–1.0436|1.0246|1.0148|
|candidate-self/p16-flat|encode|1.0114|0.8527–1.1794|0.9745–1.0887|1.0343|1.0074|
|candidate-self/p16-flat|decode|1.0341|0.8615–1.4333|0.9733–1.0826|1.0535|1.0000|
|candidate-self/p16-flat|prepare|1.0373|0.7368–1.3846|0.9053–1.1404|1.0636|0.9493|
|candidate-self/p16-flat|prepare_encode|0.9902|0.9119–1.1438|0.9493–1.0452|0.9747|1.0192|
|candidate-self/p16-ramp|encode|0.9888|0.7508–1.0837|0.9563–1.0231|0.9899|0.9888|
|candidate-self/p16-ramp|decode|0.9600|0.7489–1.1093|0.9555–1.0057|1.0033|0.9571|
|candidate-self/p16-ramp|prepare|0.9998|0.8354–1.1711|0.8848–1.0261|0.9621|1.0250|
|candidate-self/p16-ramp|prepare_encode|1.0104|0.8214–1.0641|0.9606–1.0239|1.0129|1.0063|
|candidate-self/p16-noise|encode|1.0184|0.7776–1.2261|0.9704–1.0538|1.0189|0.9998|
|candidate-self/p16-noise|decode|1.0381|0.7052–1.3068|0.8273–1.1339|0.8870|1.1151|
|candidate-self/p16-noise|prepare|1.0127|0.8500–1.2152|0.9273–1.1004|0.9330|1.0723|
|candidate-self/p16-noise|prepare_encode|1.0054|0.8634–1.2682|0.9696–1.0198|0.9919|1.0078|
|pinned-self/p12-flat|encode|0.9907|0.7674–1.0807|0.9262–1.0289|1.0142|0.9624|
|pinned-self/p12-flat|decode|0.9920|0.7927–1.1056|0.9775–1.0218|0.9920|0.9945|
|pinned-self/p12-flat|prepare|0.9939|0.7927–1.1000|0.9498–1.0524|0.9591|1.0293|
|pinned-self/p12-flat|prepare_encode|1.0131|0.8806–1.2808|0.9882–1.0298|1.0015|1.0191|
|pinned-self/p12-ramp|encode|0.9927|0.5734–1.1022|0.9456–1.0219|0.9804|1.0141|
|pinned-self/p12-ramp|decode|0.9776|0.7414–1.1216|0.9580–1.0378|0.9584|1.0220|
|pinned-self/p12-ramp|prepare|1.0005|0.7865–1.1389|0.9451–1.0937|0.9797|1.0199|
|pinned-self/p12-ramp|prepare_encode|0.9962|0.6346–1.0949|0.9668–1.0181|1.0038|0.9903|
|pinned-self/p12-noise|encode|0.9693|0.7483–1.5917|0.9406–1.0103|0.9578|0.9856|
|pinned-self/p12-noise|decode|1.0611|0.5461–1.5372|0.7600–1.1068|1.0826|0.9379|
|pinned-self/p12-noise|prepare|0.9673|0.8434–1.2286|0.9217–1.0208|0.9528|1.0003|
|pinned-self/p12-noise|prepare_encode|0.9946|0.7811–1.2239|0.9297–1.0383|0.9572|1.0152|
|pinned-self/p16-flat|encode|0.9796|0.8401–1.2165|0.9056–1.0205|1.0005|0.9621|
|pinned-self/p16-flat|decode|0.9879|0.8814–1.0843|0.9667–1.0157|1.0094|0.9754|
|pinned-self/p16-flat|prepare|0.9878|0.8537–1.1266|0.9593–1.0444|0.9640|1.0257|
|pinned-self/p16-flat|prepare_encode|1.0084|0.9020–1.0565|0.9681–1.0305|0.9789|1.0253|
|pinned-self/p16-ramp|encode|1.0056|0.8699–1.1039|0.9863–1.0304|1.0103|1.0008|
|pinned-self/p16-ramp|decode|1.0165|0.8892–1.0904|0.9931–1.0400|1.0109|1.0256|
|pinned-self/p16-ramp|prepare|1.0267|0.7766–1.2353|0.9640–1.0734|0.9934|1.0557|
|pinned-self/p16-ramp|prepare_encode|1.0000|0.9033–1.0874|0.9718–1.0223|1.0052|0.9839|
|pinned-self/p16-noise|encode|1.0165|0.9259–1.1769|0.9566–1.0404|1.0370|0.9656|
|pinned-self/p16-noise|decode|0.9351|0.8007–1.4520|0.8451–0.9953|0.9570|0.9098|
|pinned-self/p16-noise|prepare|0.9932|0.9036–1.1200|0.9552–1.0511|0.9723|1.0141|
|pinned-self/p16-noise|prepare_encode|1.0037|0.9163–1.1058|0.9798–1.0319|1.0216|0.9874|

Across48 pooled metrics, 2 exceed1.05 and 1 fall below0.95 despite identical code/binary within each control. These controls measure observed short-run label/block/order variation; they do not identify its cause or cancel a cross-producer regression. Paired process blocks, not individual iterations, form the interval unit. Shared-host temporal correlation and multiple marginal intervals limit inference. No acceptance, threshold change or extra run follows automatically.
