# Changelog

## [0.5.0](https://github.com/varghesevv/skills/compare/skills-v0.4.2...skills-v0.5.0) (2026-10-30)


### Features

* **api:** commit the OpenAPI contract and check it in CI ([261291c](https://github.com/varghesevv/skills/commit/261291c74bdf8774b9c5fe4861845192c7751eb2))
* **api:** commit the OpenAPI contract and check it in CI ([0dc60ef](https://github.com/varghesevv/skills/commit/0dc60efebbc5e7abb0fe6bc92ac8c8c54864c08f))
* **api:** public app config with role words and app versions ([b797f6b](https://github.com/varghesevv/skills/commit/b797f6bdf3a60462689eca1186054870e43720fb))
* **api:** public app config with role words and app versions ([8514c64](https://github.com/varghesevv/skills/commit/8514c64a585ac1f42f95adefaebdfe46decb5c38))
* **ci:** component-aware pull request reviewers ([45af210](https://github.com/varghesevv/skills/commit/45af21084290e9d16d5438412422027a30c76362))
* **ci:** component-aware pull request reviewers ([e65aa94](https://github.com/varghesevv/skills/commit/e65aa942fe23e4c1516bd18e0a178185fce59e7b))
* **ci:** review threads, PR overview and fork guard ([e9dcc7b](https://github.com/varghesevv/skills/commit/e9dcc7b5542b46b1fc2bdee43308e9c550780625))
* **ci:** review threads, PR overview and fork guard ([66b360d](https://github.com/varghesevv/skills/commit/66b360d0c326ceb7e83c19cf7e49f5b7355b34af))
* default reveal limits to 10 per hour and 20 per day ([b77c1fa](https://github.com/varghesevv/skills/commit/b77c1fa1fa5fc6196d1d69ec035172d0033795e4))
* hide freelancer mobile numbers behind a tracked, rate-limited reveal ([8b066f4](https://github.com/varghesevv/skills/commit/8b066f4d738732ae1a8509591142034c22050fdc))
* **mobile:** api client, token store, terminology and error messages ([b162629](https://github.com/varghesevv/skills/commit/b162629a867ee8460f36b4c5c4d91258a865be9c))
* **mobile:** API client, token store, terminology and error messages ([3b2d2ba](https://github.com/varghesevv/skills/commit/3b2d2ba9c980b14524ef8ee92e395eaa5a3305c0))
* **mobile:** mobile auth screens ([0ed9e3e](https://github.com/varghesevv/skills/commit/0ed9e3e89d1358e0e83e8b94b97c7d068a4d1a0e))
* **mobile:** welcome, login, register, forgot-password, dashboard and navigation shell ([e7783ec](https://github.com/varghesevv/skills/commit/e7783ec44946ca027d9831370b22ef71e4ccd6b2))
* phone reveal tracking implementation ([3b4a604](https://github.com/varghesevv/skills/commit/3b4a604f4a3b0a7947c9b77cd4956804dd14a5f4))
* **web:** separate role badge wording ([6c2265c](https://github.com/varghesevv/skills/commit/6c2265ca0819da1ab0964f5bd42cdc3c9df3f0ef))
* **web:** separate role badge wording ([4897d97](https://github.com/varghesevv/skills/commit/4897d97b8fe4fef314bea0b05b66800d05e4ff0a))


### Bug Fixes

* agents ([29c6f13](https://github.com/varghesevv/skills/commit/29c6f13c09635364801f42b020537e45662fc9f2))
* **api:** validate app versions against each other and list them in demo.env.example ([5b58194](https://github.com/varghesevv/skills/commit/5b581949cf255535d83ccb24593f49512e6aa21e))
* **ci:** address reviewer feedback and add fork guard check ([f7b9980](https://github.com/varghesevv/skills/commit/f7b998038ee3522e99127a04753b9e040fdea48c))
* **ci:** address reviewer feedback and add fork guard check ([076a47b](https://github.com/varghesevv/skills/commit/076a47b9f7d6c4c5b3f9ecb49bc6d1cea8aec7bb))
* **ci:** drop unsupported temperature from the Claude call ([108beec](https://github.com/varghesevv/skills/commit/108beec8c54cca07b25e6c3dd668595d8d5c17a9))
* **ci:** drop unsupported temperature from the Claude call ([26be71f](https://github.com/varghesevv/skills/commit/26be71f2175e409f6085c591ace9cc5a48dfae8d))
* **ci:** evaluate the fork guard condition instead of matching text ([904b6e6](https://github.com/varghesevv/skills/commit/904b6e6e2309cc7ebde1f62f7164fb016e95da71))
* **ci:** make the fork guard check stricter ([5a108da](https://github.com/varghesevv/skills/commit/5a108da3651dfb143f3d73fe8cd7e354eee2aa1c))
* **ci:** use gemini-3.8-flash and show model errors ([4155aab](https://github.com/varghesevv/skills/commit/4155aabaeadeaa058d0d95cc7a52125fd9d37692))
* docker issues ([e887ab2](https://github.com/varghesevv/skills/commit/e887ab242eb925234e38c31349999e3269096b75))
* join the searched-skills unnest after the reveals table ([d99446d](https://github.com/varghesevv/skills/commit/d99446dfe4ef5b680b0df156cadef208f6f85a20))
* keep the Reveal button at the 44px touch target size ([9881f0c](https://github.com/varghesevv/skills/commit/9881f0c6222b9afd4267d863f2433f683848eff2))
* **mobile:** commit the app sources the root .gitignore was hiding ([ab00d0f](https://github.com/varghesevv/skills/commit/ab00d0f794a4c96bb7b6527741ae54f81ba0b3a8))
* **mobile:** forget the refresh token only on 401 and refuse release builds without their settings ([80489bd](https://github.com/varghesevv/skills/commit/80489bd5af4cbf578eff00ef02b87a552e26b3e2))
* **mobile:** resolve role words before values, move the in-memory token store to tests and test the update screen ([61c4381](https://github.com/varghesevv/skills/commit/61c4381efbbb617dbb233278669e6c73e9981949))
* **mobile:** wire session expiry, fire it once, validate responses and neutral error texts ([4f460d8](https://github.com/varghesevv/skills/commit/4f460d887fda72574cf4484618f7c420ad40b236))
* moving to linux ([c5980dc](https://github.com/varghesevv/skills/commit/c5980dca84c849d43170049f3924f478224c3e69))
* name the unnest output column in the searched-skills query ([d98d863](https://github.com/varghesevv/skills/commit/d98d8637720bd95c233361f535879371427d67f1))
* naming conventions ([947b9dd](https://github.com/varghesevv/skills/commit/947b9dd8fdd7faf4bbd5e46bc9d25ff0454e9f23))
* optimizations from claude ([4fb588c](https://github.com/varghesevv/skills/commit/4fb588ceffd6f4584571e1aca435e5a3a0c7fdc5))
* runner docker issue ([2027caf](https://github.com/varghesevv/skills/commit/2027cafa7882c9558b69e2c3eb4168b7cd584f51))
* test fixes - claude ([07f08ed](https://github.com/varghesevv/skills/commit/07f08ed1d9fe1b44bf71eb1210d8e296c701f425))
* wrong attribute ([7f7d927](https://github.com/varghesevv/skills/commit/7f7d927f56afcc6e633653dad1c7969d3018df35))

## [0.4.2](https://github.com/varghesevv/skills/compare/skills-v0.4.1...skills-v0.4.2) (2026-10-24)


### Bug Fixes

* build errors ([b8fd37d](https://github.com/varghesevv/skills/commit/b8fd37d603e911ddbf1002d1b7f8a43cd50e8657))
* tests ([fd0ccc9](https://github.com/varghesevv/skills/commit/fd0ccc9dc8a1170849467907f30c4f74d9be2fb0))
* tests ([7801cea](https://github.com/varghesevv/skills/commit/7801cea18f1376a19f66f3ac1a46721b295df745))
* tests ([842d444](https://github.com/varghesevv/skills/commit/842d4445cb5eda0aa2f1ee604dd44b83a6a2a14b))

## [0.4.1](https://github.com/varghesevv/skills/compare/skills-v0.4.0...skills-v0.4.1) (2026-10-23)


### Bug Fixes

* removing other login links from login pages ([1e45a9f](https://github.com/varghesevv/skills/commit/1e45a9ff64254aebbadc6094ce75bc6f7624ba4b))
* removing other login links from login pages ([9e063f7](https://github.com/varghesevv/skills/commit/9e063f7ce46475c474184d82280cbfca3194b347))

## [0.4.0](https://github.com/varghesevv/skills/compare/skills-v0.3.1...skills-v0.4.0) (2026-10-23)


### Features

* add pgadmin and search update ([38c2daa](https://github.com/varghesevv/skills/commit/38c2daa03d534aa194bbe324a55c8b40633051b2))
* add pgadmin and search update ([571d2ac](https://github.com/varghesevv/skills/commit/571d2ac22ed2586518ab88c974004365e8166d10))
* search ui refinements ([1c4d1df](https://github.com/varghesevv/skills/commit/1c4d1dfe27dbd64a75a0c8d28f40d72eaa440728))

## [0.3.1](https://github.com/varghesevv/skills/compare/skills-v0.3.0...skills-v0.3.1) (2026-10-23)


### Bug Fixes

* menu navigation ([c7a1a8e](https://github.com/varghesevv/skills/commit/c7a1a8e5a1141ffa26e887e095f1845bd8046d9e))
* menu navigation ([d746427](https://github.com/varghesevv/skills/commit/d746427c61ae6bc5033d79c69e23b55e5dd40f19))
* search filter ([2e57f66](https://github.com/varghesevv/skills/commit/2e57f668ac8690001fb5c47f2539c58d265d9837))
* search filter ([8e69360](https://github.com/varghesevv/skills/commit/8e693607b4ebc448bc90b5889c28d4dba9fd03ce))

## [0.3.0](https://github.com/varghesevv/skills/compare/skills-v0.2.0...skills-v0.3.0) (2026-10-23)


### Features

* show Freelancer as Searcher in the church profile ([1a1c635](https://github.com/varghesevv/skills/commit/1a1c63525255d853b54bca40d54d83186cc6eb4a))

## [0.2.0](https://github.com/varghesevv/skills/compare/skills-v0.1.0...skills-v0.2.0) (2026-10-23)


### Features

* choose wording and web addresses per installation ([439877e](https://github.com/varghesevv/skills/commit/439877ef8b464140a67f0d59c07f81f5edadcd8b))
* choose wording and web addresses per installation ([cf96436](https://github.com/varghesevv/skills/commit/cf96436441679759e313b7099459432c92429dd9))
* feature/separate login pages ([6e7486d](https://github.com/varghesevv/skills/commit/6e7486dfa1a98fccd8ffc4b743a3c5b98024a77f))
* fix tests ([4b70625](https://github.com/varghesevv/skills/commit/4b7062574e0ca58412358816dd4368b187fc5cc2))
* semantic versions, tags and releases ([98ea93b](https://github.com/varghesevv/skills/commit/98ea93b82ce9b388ccb1bf4c96768c8c41f5f042))
* semantic versions, tags and releases ([eafbb0c](https://github.com/varghesevv/skills/commit/eafbb0cf97ec0078bb32ca178a58561fb24974d4))
* separate login pages for people, organisations and admins ([274edff](https://github.com/varghesevv/skills/commit/274edff6a4f5bccb6fd9466977edf7bb6fa003be))
* separate login pages for people, organisations and admins ([a457156](https://github.com/varghesevv/skills/commit/a457156a685b9307fd888e9eb496c20b9884b4c3))


### Bug Fixes

* run the secret check from the workspace root ([511800f](https://github.com/varghesevv/skills/commit/511800fbe770cb9e83bad5d3a7ddbfc2683258ed))
* run the secret check from the workspace root ([7e86261](https://github.com/varghesevv/skills/commit/7e86261d0f3f4ea7329bb6df81caaa351a796760))
