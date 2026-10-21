# Short-path candidate: fixed tiny comparisons

Base bee49a2ad47eae4ea149bdced2043b7a45df3dae; combined patch 7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a; binary 7f618c0cf8fe1c31bee5a36b212c0dc2943e89fd366b4228a966f63d83aa5231.

Both predeclared campaigns completed once, with16 paired process blocks across all6 cases:384 processes. Original Consumer/all4 operations and production safety checks remain intact. Ratios are candidate/pinned predecessor. No production promotion or automatic waiver.

|Mode/case|Encode|Decode|Prepare|Prepare+encode|
|---|---:|---:|---:|---:|
|short-pinned/p12-flat|0.9081|1.0661|1.0256|1.0386|
|short-pinned/p12-ramp|0.7992|1.0224|1.0526|0.9252|
|short-pinned/p12-noise|0.7286|1.0875|1.0128|0.8190|
|short-pinned/p16-flat|0.9903|1.0683|1.0062|1.0485|
|short-pinned/p16-ramp|0.8268|0.9647|1.0265|0.9198|
|short-pinned/p16-noise|0.7440|1.1371|1.0519|0.7971|
|long-pinned/p12-flat|0.9790|0.9815|0.8553|0.9462|
|long-pinned/p12-ramp|0.8489|0.8854|0.8243|0.8429|
|long-pinned/p12-noise|0.7579|0.9081|0.8592|0.7617|
|long-pinned/p16-flat|0.9862|0.9938|0.8800|0.9623|
|long-pinned/p16-ramp|0.9416|0.8981|0.9028|0.8621|
|long-pinned/p16-noise|0.7770|0.9060|0.9155|0.7324|

|Mode/case|Operation|Median pair|Block range|IQR|Reference-first|Candidate-first|
|---|---|---:|---|---|---:|---:|
|short-pinned/p12-flat|encode|0.9075|0.8106–1.9338|0.8759–0.9741|0.9091|0.9075|
|short-pinned/p12-flat|decode|1.0423|0.9415–2.3035|0.9909–1.2076|1.0506|1.0351|
|short-pinned/p12-flat|prepare|1.0006|0.8778–2.7468|0.9300–1.1021|0.9835|1.0211|
|short-pinned/p12-flat|prepare_encode|1.0246|0.8807–2.6831|0.9768–1.1155|1.0298|1.0235|
|short-pinned/p12-ramp|encode|0.8013|0.7097–1.1317|0.7568–0.9200|0.8013|0.7987|
|short-pinned/p12-ramp|decode|1.0112|0.9255–1.3917|0.9654–1.0754|1.0559|0.9719|
|short-pinned/p12-ramp|prepare|1.0384|0.8989–1.4100|0.9685–1.1283|1.0652|1.0002|
|short-pinned/p12-ramp|prepare_encode|0.9002|0.7839–1.2696|0.8755–0.9530|0.9147|0.8875|
|short-pinned/p12-noise|encode|0.7273|0.4579–0.8706|0.6885–0.7494|0.7398|0.7168|
|short-pinned/p12-noise|decode|1.1005|0.5117–1.4654|0.8214–1.3049|0.8732|1.1817|
|short-pinned/p12-noise|prepare|1.0133|0.6207–1.2917|0.9604–1.1040|1.0260|1.0005|
|short-pinned/p12-noise|prepare_encode|0.8179|0.4661–1.0306|0.7810–0.8387|0.8157|0.8261|
|short-pinned/p16-flat|encode|0.9516|0.8371–1.4169|0.8750–1.0199|0.8928|1.0136|
|short-pinned/p16-flat|decode|1.0335|0.9508–1.3704|1.0096–1.0978|1.0452|1.0189|
|short-pinned/p16-flat|prepare|1.0256|0.7317–1.2532|0.9467–1.0660|1.0501|0.9779|
|short-pinned/p16-flat|prepare_encode|1.0419|0.8901–1.3107|0.9843–1.1295|1.1130|1.0007|
|short-pinned/p16-ramp|encode|0.8422|0.7104–1.0408|0.8028–0.8543|0.8475|0.8285|
|short-pinned/p16-ramp|decode|0.9693|0.8633–1.1440|0.9202–1.0100|0.9622|0.9698|
|short-pinned/p16-ramp|prepare|1.0403|0.8000–1.1765|0.9831–1.0816|1.0403|1.0201|
|short-pinned/p16-ramp|prepare_encode|0.9193|0.7984–1.2006|0.9066–0.9527|0.9193|0.9262|
|short-pinned/p16-noise|encode|0.7238|0.6004–0.9089|0.6976–0.7602|0.7336|0.7140|
|short-pinned/p16-noise|decode|1.0714|0.8852–1.5661|0.9835–1.1469|1.1141|1.0115|
|short-pinned/p16-noise|prepare|1.0597|0.9178–1.2319|0.9780–1.1287|1.1174|1.0142|
|short-pinned/p16-noise|prepare_encode|0.7872|0.6702–0.9701|0.7687–0.8261|0.8075|0.7814|
|long-pinned/p12-flat|encode|0.9774|0.9621–1.0108|0.9712–0.9859|0.9824|0.9739|
|long-pinned/p12-flat|decode|0.9830|0.9550–1.0095|0.9783–0.9876|0.9860|0.9815|
|long-pinned/p12-flat|prepare|0.8675|0.8462–0.9028|0.8553–0.8788|0.8684|0.8610|
|long-pinned/p12-flat|prepare_encode|0.9491|0.9233–0.9615|0.9454–0.9523|0.9470|0.9493|
|long-pinned/p12-ramp|encode|0.8482|0.7604–0.9861|0.8149–0.8548|0.8207|0.8528|
|long-pinned/p12-ramp|decode|0.9060|0.8262–1.0412|0.8788–0.9161|0.8928|0.9135|
|long-pinned/p12-ramp|prepare|0.8164|0.7922–0.9452|0.8026–0.8243|0.8067|0.8231|
|long-pinned/p12-ramp|prepare_encode|0.8449|0.7891–0.9451|0.8237–0.8473|0.8309|0.8461|
|long-pinned/p12-noise|encode|0.7564|0.6716–0.7973|0.7500–0.7584|0.7546|0.7564|
|long-pinned/p12-noise|decode|0.9060|0.8042–0.9705|0.8972–0.9118|0.9029|0.9081|
|long-pinned/p12-noise|prepare|0.8581|0.7922–0.9577|0.8410–0.8609|0.8472|0.8592|
|long-pinned/p12-noise|prepare_encode|0.7599|0.6841–0.8327|0.7496–0.7618|0.7552|0.7605|
|long-pinned/p16-flat|encode|0.9862|0.9691–1.0480|0.9759–0.9991|0.9896|0.9843|
|long-pinned/p16-flat|decode|0.9939|0.9754–1.0455|0.9816–1.0076|0.9954|0.9938|
|long-pinned/p16-flat|prepare|0.8800|0.8553–0.9306|0.8684–0.8842|0.8750|0.8800|
|long-pinned/p16-flat|prepare_encode|0.9637|0.8964–1.0126|0.9591–0.9779|0.9621|0.9684|
|long-pinned/p16-ramp|encode|0.9419|0.8795–0.9574|0.9135–0.9475|0.9133|0.9444|
|long-pinned/p16-ramp|decode|0.8956|0.8335–0.9506|0.8897–0.9030|0.8990|0.8946|
|long-pinned/p16-ramp|prepare|0.8967|0.8101–0.9286|0.8889–0.9155|0.8896|0.9021|
|long-pinned/p16-ramp|prepare_encode|0.8597|0.8160–0.9102|0.8553–0.8697|0.8613|0.8587|
|long-pinned/p16-noise|encode|0.7698|0.7304–0.8131|0.7552–0.7856|0.7612|0.7779|
|long-pinned/p16-noise|decode|0.8980|0.8740–0.9953|0.8836–0.9217|0.8923|0.9051|
|long-pinned/p16-noise|prepare|0.9149|0.8312–0.9444|0.8979–0.9288|0.9085|0.9149|
|long-pinned/p16-noise|prepare_encode|0.7341|0.6975–0.8060|0.7269–0.7457|0.7322|0.7358|

All paired ratios/deltas and the predeclared bootstrap/conservative intervals are retained. These use the process pair as the unit; individual iterations are not independent replicates. Shared-session correlation and marginal multiple-metric intervals limit inference; four-block larger-image evidence must remain separate. Adverse/order-dependent outcomes are retained.
