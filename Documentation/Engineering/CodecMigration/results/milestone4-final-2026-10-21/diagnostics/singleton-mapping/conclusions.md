# Singleton mapping candidate: fixed comparison results

Candidate base: bee49a2ad47eae4ea149bdced2043b7a45df3dae. Patch: 612f149b32accabc7d78983c13c965b064084398f6af9505f49dab27509051b8. Binary: ce251000422daaacae4074528689c4c57330f5a92d107e40a0aa49b92bb877c8.

All four fixed comparisons completed once, 192 processes each (768 total), with original Consumer unchanged and all four operations retained. Each case has 16 balanced paired blocks. Short = 5 warmups/5 observations; long = 20,000/1,000. No production changes or promotion.

Ratios below are candidate/reference. `bee` is the current source baseline; `pinned` is JLSwift 15aa751. These tables retain all outcomes, including regressions.

|Comparison|Case|Encode|Decode|Prepare|Prepare+encode|
|---|---|---:|---:|---:|---:|
|short-bee|p12-flat|1.0075|0.9460|0.8588|0.9959|
|short-bee|p12-ramp|0.9950|0.9866|0.8011|1.0008|
|short-bee|p12-noise|1.0301|0.9817|0.8864|1.0179|
|short-bee|p16-flat|1.0385|0.9188|0.8202|1.0081|
|short-bee|p16-ramp|0.9805|0.9658|0.8122|0.9883|
|short-bee|p16-noise|1.0642|1.0490|0.9030|1.0061|
|short-pinned|p12-flat|0.9169|1.1243|0.9744|1.0397|
|short-pinned|p12-ramp|0.8154|0.9715|0.9221|0.9337|
|short-pinned|p12-noise|0.7084|1.2694|1.0274|0.8335|
|short-pinned|p16-flat|0.8250|1.1163|0.9557|1.0398|
|short-pinned|p16-ramp|0.8065|0.9834|1.0067|0.9521|
|short-pinned|p16-noise|0.6913|1.0598|0.9872|0.7940|
|long-bee|p12-flat|0.9964|0.9852|0.9265|0.9801|
|long-bee|p12-ramp|0.9542|0.9568|0.8923|0.9589|
|long-bee|p12-noise|0.9929|0.9903|0.9385|0.9863|
|long-bee|p16-flat|0.9982|0.9881|0.9265|0.9804|
|long-bee|p16-ramp|0.9948|1.0087|0.9394|0.9964|
|long-bee|p16-noise|1.0000|0.9704|0.9242|0.9723|
|long-pinned|p12-flat|0.9789|1.0279|0.8400|0.9367|
|long-pinned|p12-ramp|0.8593|0.9310|0.7945|0.8454|
|long-pinned|p12-noise|0.7729|0.9668|0.8592|0.7692|
|long-pinned|p16-flat|0.9827|1.0338|0.8421|0.9437|
|long-pinned|p16-ramp|0.9239|0.9134|0.8611|0.8585|
|long-pinned|p16-noise|0.7593|0.9547|0.8611|0.7455|

All-operation paired-block spread and order summaries:

|Comparison/case|Operation|Median pair|Block range|IQR|Reference-first|Candidate-first|
|---|---|---:|---|---|---:|---:|
|short-bee/p12-flat|encode|0.9822|0.7365–2.0667|0.9235–1.1240|0.9981|0.9715|
|short-bee/p12-flat|decode|0.9562|0.7785–1.9892|0.8848–0.9777|0.9481|0.9600|
|short-bee/p12-flat|prepare|0.8850|0.6792–1.5682|0.7962–0.9279|0.8925|0.8794|
|short-bee/p12-flat|prepare_encode|0.9918|0.7228–2.1214|0.9414–1.0369|0.9520|1.0138|
|short-bee/p12-ramp|encode|1.0103|0.9259–1.2070|0.9749–1.0459|0.9899|1.0504|
|short-bee/p12-ramp|decode|0.9786|0.8117–1.1729|0.9564–1.0425|0.9771|0.9944|
|short-bee/p12-ramp|prepare|0.7884|0.6961–1.0506|0.7494–0.9030|0.7513|0.8441|
|short-bee/p12-ramp|prepare_encode|1.0025|0.9165–1.2193|0.9801–1.0650|0.9902|1.0228|
|short-bee/p12-noise|encode|1.0373|0.7728–1.2004|0.9852–1.0575|0.9881|1.0546|
|short-bee/p12-noise|decode|0.9985|0.5492–1.7030|0.9441–1.1585|0.9630|1.0576|
|short-bee/p12-noise|prepare|0.9012|0.5328–1.0000|0.8704–0.9407|0.9087|0.9012|
|short-bee/p12-noise|prepare_encode|1.0357|0.8616–1.2705|0.9762–1.0747|1.0175|1.0453|
|short-bee/p16-flat|encode|1.0042|0.6704–1.3445|0.9521–1.0808|0.9899|1.0347|
|short-bee/p16-flat|decode|0.9516|0.7534–1.1303|0.8915–0.9841|0.9610|0.9290|
|short-bee/p16-flat|prepare|0.7791|0.5702–1.0380|0.7395–0.8415|0.7569|0.8224|
|short-bee/p16-flat|prepare_encode|1.0082|0.7942–1.4035|0.9633–1.0444|1.0082|1.0098|
|short-bee/p16-ramp|encode|0.9759|0.8756–1.2817|0.9549–1.0295|0.9945|0.9703|
|short-bee/p16-ramp|decode|0.9701|0.6951–1.1199|0.8917–1.0199|0.9701|0.9516|
|short-bee/p16-ramp|prepare|0.8297|0.6667–1.1370|0.7650–0.9008|0.8434|0.8248|
|short-bee/p16-ramp|prepare_encode|0.9937|0.7938–1.2203|0.9638–1.0580|0.9937|0.9931|
|short-bee/p16-noise|encode|1.0501|0.9141–1.2891|1.0155–1.1833|1.1629|1.0349|
|short-bee/p16-noise|decode|1.0391|0.7650–1.4012|0.9363–1.2191|1.0512|1.0391|
|short-bee/p16-noise|prepare|0.8766|0.7474–1.0667|0.8383–1.0000|0.9249|0.8692|
|short-bee/p16-noise|prepare_encode|0.9961|0.9264–1.2196|0.9644–1.0598|0.9816|1.0092|
|short-pinned/p12-flat|encode|0.8946|0.7383–1.1523|0.8301–0.9578|0.9056|0.8377|
|short-pinned/p12-flat|decode|1.0939|0.9328–1.4752|1.0739–1.2292|1.1814|1.0860|
|short-pinned/p12-flat|prepare|0.9611|0.7976–1.1892|0.9263–1.0000|0.9875|0.9483|
|short-pinned/p12-flat|prepare_encode|1.0564|0.7861–1.3626|1.0063–1.1254|1.0461|1.0705|
|short-pinned/p12-ramp|encode|0.8276|0.7481–0.9315|0.7917–0.8444|0.8319|0.8201|
|short-pinned/p12-ramp|decode|0.9653|0.6849–1.1123|0.9345–0.9880|0.9302|0.9709|
|short-pinned/p12-ramp|prepare|0.9194|0.8090–1.0400|0.8956–0.9370|0.9178|0.9204|
|short-pinned/p12-ramp|prepare_encode|0.9128|0.7997–0.9859|0.8829–0.9350|0.9206|0.9069|
|short-pinned/p12-noise|encode|0.7063|0.6265–0.8135|0.6902–0.7374|0.6995|0.7231|
|short-pinned/p12-noise|decode|1.2883|0.6438–1.7885|1.0856–1.4098|1.2242|1.2883|
|short-pinned/p12-noise|prepare|1.0406|0.8889–1.3026|0.9932–1.1007|1.0202|1.0617|
|short-pinned/p12-noise|prepare_encode|0.8250|0.6845–0.9308|0.7998–0.8509|0.8289|0.8250|
|short-pinned/p16-flat|encode|0.8277|0.6630–1.1062|0.7784–0.8948|0.8377|0.8186|
|short-pinned/p16-flat|decode|1.1330|0.8940–1.3529|1.0280–1.2585|1.0753|1.1657|
|short-pinned/p16-flat|prepare|0.9493|0.8333–1.1528|0.8916–1.0203|0.9015|1.0065|
|short-pinned/p16-flat|prepare_encode|1.0509|0.7696–1.4559|1.0016–1.1423|1.0193|1.1238|
|short-pinned/p16-ramp|encode|0.8146|0.7394–0.8990|0.7936–0.8280|0.8146|0.8114|
|short-pinned/p16-ramp|decode|0.9764|0.8603–1.1076|0.9327–1.0039|0.9840|0.9619|
|short-pinned/p16-ramp|prepare|0.9672|0.8072–1.2754|0.9213–1.0616|0.9868|0.9672|
|short-pinned/p16-ramp|prepare_encode|0.9283|0.9001–1.0689|0.9188–0.9469|0.9311|0.9283|
|short-pinned/p16-noise|encode|0.6968|0.6073–0.8083|0.6607–0.7140|0.6630|0.7010|
|short-pinned/p16-noise|decode|1.1622|0.8587–1.4476|0.9454–1.2995|0.9678|1.2170|
|short-pinned/p16-noise|prepare|1.0000|0.8352–1.2368|0.8781–1.0164|0.9366|1.0131|
|short-pinned/p16-noise|prepare_encode|0.7938|0.6969–0.8982|0.7510–0.8104|0.7944|0.7938|
|long-bee/p12-flat|encode|0.9964|0.9517–1.0540|0.9907–1.0009|0.9946|0.9964|
|long-bee/p12-flat|decode|0.9851|0.9621–1.0417|0.9791–0.9940|0.9851|0.9837|
|long-bee/p12-flat|prepare|0.9371|0.9118–0.9851|0.9249–0.9414|0.9371|0.9334|
|long-bee/p12-flat|prepare_encode|0.9818|0.9453–1.0316|0.9766–0.9875|0.9802|0.9833|
|long-bee/p12-ramp|encode|0.9476|0.8895–1.1797|0.9002–0.9981|0.9234|0.9934|
|long-bee/p12-ramp|decode|0.9486|0.8995–1.1071|0.9147–0.9870|0.9307|0.9787|
|long-bee/p12-ramp|prepare|0.8738|0.8169–1.0635|0.8358–0.9355|0.8417|0.9201|
|long-bee/p12-ramp|prepare_encode|0.9462|0.8862–1.0986|0.9041–0.9884|0.9291|0.9742|
|long-bee/p12-noise|encode|0.9991|0.8964–1.0988|0.9737–1.0072|0.9991|1.0018|
|long-bee/p12-noise|decode|0.9946|0.9143–1.1072|0.9725–1.0132|0.9908|1.0001|
|long-bee/p12-noise|prepare|0.9196|0.8551–1.0469|0.9018–0.9421|0.9150|0.9308|
|long-bee/p12-noise|prepare_encode|0.9836|0.9222–1.0911|0.9737–1.0021|0.9819|0.9905|
|long-bee/p16-flat|encode|0.9965|0.9564–1.0279|0.9929–1.0044|0.9947|1.0000|
|long-bee/p16-flat|decode|0.9851|0.9764–1.0266|0.9794–0.9948|0.9837|0.9866|
|long-bee/p16-flat|prepare|0.9371|0.9130–0.9706|0.9265–0.9412|0.9301|0.9403|
|long-bee/p16-flat|prepare_encode|0.9804|0.9674–1.0195|0.9710–0.9845|0.9740|0.9820|
|long-bee/p16-ramp|encode|0.9974|0.9128–1.0717|0.9722–1.0344|1.0192|0.9854|
|long-bee/p16-ramp|decode|1.0154|0.8853–1.0845|0.9907–1.0217|1.0172|1.0096|
|long-bee/p16-ramp|prepare|0.9389|0.8592–1.0000|0.9251–0.9540|0.9466|0.9319|
|long-bee/p16-ramp|prepare_encode|0.9978|0.8864–1.0874|0.9829–1.0132|1.0055|0.9937|
|long-bee/p16-noise|encode|0.9968|0.8940–1.0587|0.9639–1.0309|0.9968|1.0095|
|long-bee/p16-noise|decode|0.9797|0.9091–1.0569|0.9332–1.0107|0.9690|0.9916|
|long-bee/p16-noise|prepare|0.9454|0.8429–1.0317|0.8809–0.9570|0.9308|0.9531|
|long-bee/p16-noise|prepare_encode|0.9738|0.9086–1.0617|0.9280–0.9896|0.9549|0.9816|
|long-pinned/p12-flat|encode|0.9754|0.9549–1.0106|0.9719–0.9851|0.9722|0.9859|
|long-pinned/p12-flat|decode|1.0305|0.9970–1.0692|1.0228–1.0349|1.0291|1.0308|
|long-pinned/p12-flat|prepare|0.8400|0.8101–0.8750|0.8331–0.8533|0.8400|0.8467|
|long-pinned/p12-flat|prepare_encode|0.9380|0.8698–0.9773|0.9305–0.9443|0.9395|0.9374|
|long-pinned/p12-ramp|encode|0.8530|0.7787–0.9549|0.8412–0.8609|0.8517|0.8548|
|long-pinned/p12-ramp|decode|0.9353|0.8571–1.0222|0.9111–0.9411|0.9255|0.9376|
|long-pinned/p12-ramp|prepare|0.7945|0.7532–0.9296|0.7733–0.8062|0.7865|0.7945|
|long-pinned/p12-ramp|prepare_encode|0.8427|0.7822–0.9575|0.8385–0.8522|0.8412|0.8443|
|long-pinned/p12-noise|encode|0.7627|0.7273–0.8420|0.7548–0.8017|0.7647|0.7626|
|long-pinned/p12-noise|decode|0.9443|0.8871–1.0255|0.9324–0.9941|0.9476|0.9411|
|long-pinned/p12-noise|prepare|0.8429|0.7867–0.9571|0.8166–0.9046|0.8500|0.8369|
|long-pinned/p12-noise|prepare_encode|0.7647|0.7126–0.8523|0.7512–0.7940|0.7681|0.7637|
|long-pinned/p16-flat|encode|0.9861|0.9727–1.2478|0.9792–0.9940|0.9827|0.9861|
|long-pinned/p16-flat|decode|1.0287|1.0185–1.1915|1.0268–1.0476|1.0287|1.0358|
|long-pinned/p16-flat|prepare|0.8421|0.7778–0.9143|0.8378–0.8486|0.8421|0.8411|
|long-pinned/p16-flat|prepare_encode|0.9496|0.9200–0.9809|0.9398–0.9567|0.9494|0.9496|
|long-pinned/p16-ramp|encode|0.9027|0.8351–0.9836|0.8850–0.9293|0.8951|0.9225|
|long-pinned/p16-ramp|decode|0.9115|0.8544–1.0087|0.8856–0.9373|0.9115|0.9214|
|long-pinned/p16-ramp|prepare|0.8601|0.8026–0.9028|0.8258–0.8732|0.8441|0.8732|
|long-pinned/p16-ramp|prepare_encode|0.8610|0.8024–0.9319|0.8445–0.8777|0.8553|0.8700|
|long-pinned/p16-noise|encode|0.7442|0.6794–0.8148|0.7233–0.7795|0.7247|0.7720|
|long-pinned/p16-noise|decode|0.9294|0.8406–1.0268|0.9091–0.9791|0.9127|0.9819|
|long-pinned/p16-noise|prepare|0.8705|0.7763–0.9437|0.8250–0.9018|0.8333|0.9021|
|long-pinned/p16-noise|prepare_encode|0.7337|0.7011–0.8128|0.7227–0.7545|0.7258|0.7599|

The 16-block percentile-bootstrap and conservative order-statistic intervals are retained in summary.json/combined-summary.json. Their independent/exchangeable-block assumptions may not hold fully for a shared host/session; intervals are marginal across 24 metrics, not simultaneous. Individual timing iterations are not independent replicates. No performance acceptance follows automatically.

The targeted allocation is source-proven unreachable for singleton mappings; its existing 80-byte size was measured on Linux at the baseline. No candidate heap profile or macOS allocation-size measurement was performed.

## Findings and limits

Against bee49a2, preparation pooled ratios improved in every case: 0.8011–0.9030 in short mode and 0.8923–0.9394 in long mode. Long-mode flat preparation paired median deltas are about −0.177 µs, and flat decode paired median deltas about −0.208 µs. Thus the measured improvement is smaller than the initial speculative 0.3–0.6 µs target in the long profile.

Short-mode flat decode improves against bee49a2 (pooled 0.9460 and 0.9188) but remains above the pinned predecessor (1.1243 and 1.1163). Pinned short-mode noise decode also exceeds 1.05: 1.2694 at 12 bits and 1.0598 at 16 bits. The short bee comparison's 16-bit noise encode ratio is 1.0642; its conservative median interval includes 1, and this adverse result remains in the record.

All long-mode pooled ratios are below 1.05 against both references, but this does not erase the short-mode results. Long pinned 16-bit flat decode has four of sixteen blocks above 1.05 and a conservative median interval extending to 1.0525. The singleton change has a measured preparation benefit and modest long-profile flat decode benefit, but does not by itself close the remaining performance gate. No production promotion was performed.
