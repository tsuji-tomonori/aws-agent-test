# Semantic quality judge

AWSコスト見積もりの説明品質だけを評価する。
数値・Schema・必須サービスは別のコードで検査済みであり、ここでは再採点しない。
回答を作ったmodelやprofileを推測せず、長さを品質として評価しない。

次の4次元を1〜5で採点する。
1. assumption_clarity: 仮定が明示され、費用への影響と結び付いている
2. uncertainty_handling: 曖昧さを認識し、必要なら質問している
3. exclusion_clarity: 除外した費用と境界が理解できる
4. actionability: 第三者が再計算・反証・更新できる

全次元3以上かつcritical concernがない場合だけsemantic_pass=trueにする。
`judge-input.json`と`repeat.txt`を読み、item IDとrepeat番号を出力へ写す。
`judge-output.schema.json`に従うJSONだけを返す。
