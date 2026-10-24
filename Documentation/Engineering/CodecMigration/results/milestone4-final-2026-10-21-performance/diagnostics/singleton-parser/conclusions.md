# Combined singleton and parser candidate: fixed results

Base bee49a2ad47eae4ea149bdced2043b7a45df3dae; patch 3afd6dfb994b20e53cc794b94a85820dbaeb809691e00f088303507276496428; binary efcc88866754879eafc961933918735026bc74c897d8de65bff6e5f6f449bdd5.

Both predeclared campaigns completed once: 16 paired blocks across six scalar cases, 192 processes each, 384 total. Original Consumer and all four operations retained. No production promotion or automatic acceptance.

|Mode/case|Encode|Decode|Prepare|Prepare+encode|
|---|---:|---:|---:|---:|
|short-pinned/p12-flat|0.8939|1.0852|0.9877|1.0232|
|short-pinned/p12-ramp|0.8342|1.0266|1.0327|0.9398|
|short-pinned/p12-noise|0.7370|1.0038|1.0194|0.8117|
|short-pinned/p16-flat|0.8818|1.0555|1.0186|1.0438|
|short-pinned/p16-ramp|0.8566|0.9665|1.0327|0.9295|
|short-pinned/p16-noise|0.7086|1.1289|1.0263|0.7932|
|long-pinned/p12-flat|0.9789|1.0186|0.8667|0.9522|
|long-pinned/p12-ramp|0.8545|0.9293|0.8108|0.8456|
|long-pinned/p12-noise|0.7681|0.9495|0.8750|0.7659|
|long-pinned/p16-flat|0.9758|1.0154|0.8684|0.9528|
|long-pinned/p16-ramp|0.9251|0.9147|0.8767|0.8643|
|long-pinned/p16-noise|0.7767|0.9107|0.9014|0.7275|

All ratios are candidate/pinned predecessor. Paired-block spread and observation-order summaries:

|Mode/case|Operation|Median pair|Range|IQR|Reference-first|Candidate-first|
|---|---|---:|---|---|---:|---:|
|short-pinned/p12-flat|encode|0.8964|0.6767–1.1621|0.7914–1.0000|0.9263|0.8596|
|short-pinned/p12-flat|decode|1.0849|0.8942–1.3823|1.0075–1.1363|1.1151|1.0611|
|short-pinned/p12-flat|prepare|0.9871|0.8462–1.3494|0.9382–1.1160|1.1195|0.9628|
|short-pinned/p12-flat|prepare_encode|1.0045|0.8557–1.1313|0.9584–1.0824|1.0643|0.9986|
|short-pinned/p12-ramp|encode|0.8234|0.7523–1.0403|0.8105–0.8725|0.8152|0.8301|
|short-pinned/p12-ramp|decode|1.0394|0.8605–1.1325|1.0131–1.0786|1.0384|1.0554|
|short-pinned/p12-ramp|prepare|1.0068|0.9259–1.1855|0.9749–1.0619|0.9868|1.0338|
|short-pinned/p12-ramp|prepare_encode|0.9299|0.8802–1.0676|0.9069–0.9487|0.9112|0.9442|
|short-pinned/p12-noise|encode|0.7408|0.6412–0.9706|0.6912–0.7668|0.7413|0.7374|
|short-pinned/p12-noise|decode|0.9464|0.7233–2.0890|0.8335–1.1834|0.8677|1.0744|
|short-pinned/p12-noise|prepare|1.0190|0.9024–1.4714|0.9871–1.0868|1.0342|1.0190|
|short-pinned/p12-noise|prepare_encode|0.7996|0.5716–1.0444|0.7820–0.8383|0.7946|0.8181|
|short-pinned/p16-flat|encode|0.8868|0.7376–1.1184|0.8267–1.0136|0.9903|0.8543|
|short-pinned/p16-flat|decode|1.0780|0.8010–1.2006|1.0202–1.1531|1.1043|1.0728|
|short-pinned/p16-flat|prepare|1.0200|0.8250–1.3494|0.9613–1.1052|1.0696|1.0067|
|short-pinned/p16-flat|prepare_encode|1.0634|0.8142–1.4209|1.0122–1.1092|1.0479|1.0710|
|short-pinned/p16-ramp|encode|0.8542|0.7086–1.0876|0.8105–0.9080|0.8738|0.8329|
|short-pinned/p16-ramp|decode|0.9450|0.6937–1.0752|0.9078–0.9902|0.9874|0.9254|
|short-pinned/p16-ramp|prepare|1.0316|0.7125–1.4412|0.9215–1.0773|1.0328|1.0269|
|short-pinned/p16-ramp|prepare_encode|0.9261|0.6312–0.9971|0.8934–0.9496|0.9292|0.9091|
|short-pinned/p16-noise|encode|0.7073|0.6573–0.7548|0.6852–0.7237|0.7009|0.7147|
|short-pinned/p16-noise|decode|1.1357|0.6336–1.3947|0.9646–1.2485|1.1399|1.1152|
|short-pinned/p16-noise|prepare|1.0193|0.9136–1.2500|0.9800–1.0564|0.9931|1.0596|
|short-pinned/p16-noise|prepare_encode|0.7761|0.7403–0.8280|0.7568–0.8145|0.7668|0.7786|
|long-pinned/p12-flat|encode|0.9860|0.9517–1.4082|0.9721–0.9947|0.9825|0.9895|
|long-pinned/p12-flat|decode|1.0278|0.9819–1.3042|1.0062–1.0392|1.0216|1.0296|
|long-pinned/p12-flat|prepare|0.8734|0.8333–0.9155|0.8667–0.8908|0.8734|0.8734|
|long-pinned/p12-flat|prepare_encode|0.9556|0.9052–1.0683|0.9432–0.9732|0.9569|0.9507|
|long-pinned/p12-ramp|encode|0.8492|0.7904–0.9861|0.8223–0.8636|0.8428|0.8551|
|long-pinned/p12-ramp|decode|0.9272|0.8594–1.0594|0.9172–0.9450|0.9272|0.9312|
|long-pinned/p12-ramp|prepare|0.8219|0.7792–0.9583|0.8020–0.8405|0.8219|0.8288|
|long-pinned/p12-ramp|prepare_encode|0.8486|0.7895–0.9465|0.8309–0.8577|0.8505|0.8482|
|long-pinned/p12-noise|encode|0.7624|0.6952–0.8532|0.7390–0.7723|0.7507|0.7662|
|long-pinned/p12-noise|decode|0.9353|0.8385–1.0447|0.9002–0.9446|0.9195|0.9387|
|long-pinned/p12-noise|prepare|0.8699|0.7949–0.9857|0.8250–0.8816|0.8699|0.8671|
|long-pinned/p12-noise|prepare_encode|0.7558|0.6918–0.8813|0.7369–0.7733|0.7623|0.7523|
|long-pinned/p16-flat|encode|0.9757|0.9622–1.0000|0.9689–0.9835|0.9724|0.9758|
|long-pinned/p16-flat|decode|1.0154|1.0000–1.0463|1.0061–1.0225|1.0139|1.0170|
|long-pinned/p16-flat|prepare|0.8684|0.8442–0.8816|0.8667–0.8800|0.8734|0.8684|
|long-pinned/p16-flat|prepare_encode|0.9560|0.9319–0.9718|0.9495–0.9621|0.9530|0.9591|
|long-pinned/p16-ramp|encode|0.9162|0.8238–1.0130|0.9046–0.9407|0.9155|0.9231|
|long-pinned/p16-ramp|decode|0.9168|0.8411–1.0270|0.8981–0.9629|0.9244|0.9090|
|long-pinned/p16-ramp|prepare|0.8803|0.8077–0.9437|0.8551–0.9014|0.8881|0.8691|
|long-pinned/p16-ramp|prepare_encode|0.8632|0.7943–0.9590|0.8459–0.8815|0.8757|0.8596|
|long-pinned/p16-noise|encode|0.7657|0.6878–0.8223|0.7449–0.7786|0.7599|0.7663|
|long-pinned/p16-noise|decode|0.8980|0.8519–1.0197|0.8904–0.9193|0.9154|0.8948|
|long-pinned/p16-noise|prepare|0.8889|0.8077–0.9857|0.8869–0.9046|0.8937|0.8889|
|long-pinned/p16-noise|prepare_encode|0.7235|0.6538–0.8185|0.7189–0.7321|0.7332|0.7202|

Intervals in combined-summary.json and original summary.json use paired process blocks; serial iterations are not independent replicates. Independence/exchangeability assumptions may be affected by a shared host/session. Intervals are marginal across metrics and do not establish general bounds or automatic acceptance. All adverse results and partial-block variation remain retained.
