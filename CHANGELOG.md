# Change Log

## [0.11.0](https://github.com/theolind/pymysensors/tree/0.11.0) (2017-08-21)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.10...0.11.0)

**Merged pull requests:**

- Add debug timer logging if handle queue is slow [\#105](https://github.com/theolind/pymysensors/pull/105) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update gen\_changelog and release procedure [\#104](https://github.com/theolind/pymysensors/pull/104) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update type schema and add message tests [\#103](https://github.com/theolind/pymysensors/pull/103) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add validation of message and child values [\#102](https://github.com/theolind/pymysensors/pull/102) [[breaking change](https://github.com/theolind/pymysensors/labels/breaking%20change)] ([MartinHjelmare](https://github.com/MartinHjelmare))
- Upgrade test requirements [\#101](https://github.com/theolind/pymysensors/pull/101) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update const for version 1.5 and 2.0 [\#100](https://github.com/theolind/pymysensors/pull/100) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix subscription to topics with nested prefix [\#99](https://github.com/theolind/pymysensors/pull/99) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.10](https://github.com/theolind/pymysensors/tree/0.10) (2017-05-06)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.9.1...0.10)

**Closed issues:**

- Publish pymysensors on pypi [\#94](https://github.com/theolind/pymysensors/issues/94)

**Merged pull requests:**

- 0.10 [\#98](https://github.com/theolind/pymysensors/pull/98) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add release instructions and update setup [\#97](https://github.com/theolind/pymysensors/pull/97) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add manifest and update setup files [\#96](https://github.com/theolind/pymysensors/pull/96) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add changelog [\#95](https://github.com/theolind/pymysensors/pull/95) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.9.1](https://github.com/theolind/pymysensors/tree/0.9.1) (2017-04-11)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.9...0.9.1)

**Merged pull requests:**

- 0.9.1 [\#93](https://github.com/theolind/pymysensors/pull/93) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix pickle persistence when upgrading to 0.9 [\#92](https://github.com/theolind/pymysensors/pull/92) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.9](https://github.com/theolind/pymysensors/tree/0.9) (2017-04-03)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.8...0.9)

**Closed issues:**

- Use of OTA with MYSBootloader [\#82](https://github.com/theolind/pymysensors/issues/82)
- Question: Information in event callback [\#76](https://github.com/theolind/pymysensors/issues/76)

**Merged pull requests:**

- 0.9 [\#90](https://github.com/theolind/pymysensors/pull/90) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update readme about message structure [\#89](https://github.com/theolind/pymysensors/pull/89) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update readme about support for bootloaders [\#88](https://github.com/theolind/pymysensors/pull/88) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix ota with persistence [\#87](https://github.com/theolind/pymysensors/pull/87) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add Message method modify [\#86](https://github.com/theolind/pymysensors/pull/86) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add more envs to tox and travis [\#85](https://github.com/theolind/pymysensors/pull/85) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Move gateways into separate modules [\#84](https://github.com/theolind/pymysensors/pull/84) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Return local time instead of UTC time from Controller [\#81](https://github.com/theolind/pymysensors/pull/81) ([proddy](https://github.com/proddy))
- Add discover [\#79](https://github.com/theolind/pymysensors/pull/79) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Event callback extensions [\#78](https://github.com/theolind/pymysensors/pull/78) [[breaking change](https://github.com/theolind/pymysensors/labels/breaking%20change)] ([steve-bate](https://github.com/steve-bate))
- tcp\_check to reconnect in case of connection lost [\#67](https://github.com/theolind/pymysensors/pull/67) ([afeno](https://github.com/afeno))

## [0.8](https://github.com/theolind/pymysensors/tree/0.8) (2016-10-19)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.7.1...0.8)

**Closed issues:**

- Sensors loaded through persistence does not trigger subscription [\#70](https://github.com/theolind/pymysensors/issues/70)

**Merged pull requests:**

- 0.8 [\#75](https://github.com/theolind/pymysensors/pull/75) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix init call order [\#74](https://github.com/theolind/pymysensors/pull/74) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix support for stream message type in MQTTGateway [\#73](https://github.com/theolind/pymysensors/pull/73) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix MQTT persistence [\#72](https://github.com/theolind/pymysensors/pull/72) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix parse message to mqtt topic [\#71](https://github.com/theolind/pymysensors/pull/71) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix changing attributes on existing sensor [\#69](https://github.com/theolind/pymysensors/pull/69) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix log spam by disconnecting at serial exception [\#68](https://github.com/theolind/pymysensors/pull/68) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.7.1](https://github.com/theolind/pymysensors/tree/0.7.1) (2016-08-21)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.7...0.7.1)

**Closed issues:**

- Upgrade 0.7: Missing attributes after loading persistence file [\#65](https://github.com/theolind/pymysensors/issues/65)

**Merged pull requests:**

- Hotfix 0.7.1 [\#66](https://github.com/theolind/pymysensors/pull/66) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix persistence with missing attributes [\#64](https://github.com/theolind/pymysensors/pull/64) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.7](https://github.com/theolind/pymysensors/tree/0.7) (2016-08-20)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.6...0.7)

**Closed issues:**

- Support for the 2.0 mysensors / Local Sensor on Gateway [\#51](https://github.com/theolind/pymysensors/issues/51)
- Reading garbage after reconnect with pyserial 2.7-3.0 [\#12](https://github.com/theolind/pymysensors/issues/12)

**Merged pull requests:**

- 0.7 [\#63](https://github.com/theolind/pymysensors/pull/63) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update readme with new features [\#62](https://github.com/theolind/pymysensors/pull/62) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add more unit tests [\#61](https://github.com/theolind/pymysensors/pull/61) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add child description [\#60](https://github.com/theolind/pymysensors/pull/60) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix disconnect while tread loop is still running [\#59](https://github.com/theolind/pymysensors/pull/59) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix default MQTT topic prefix [\#58](https://github.com/theolind/pymysensors/pull/58) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add request for re-presentation of node [\#57](https://github.com/theolind/pymysensors/pull/57) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add OTA firmware update feature [\#56](https://github.com/theolind/pymysensors/pull/56) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix continue on numbered list [\#55](https://github.com/theolind/pymysensors/pull/55) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add how to contribute [\#54](https://github.com/theolind/pymysensors/pull/54) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update readme [\#53](https://github.com/theolind/pymysensors/pull/53) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix and add missing set,req and internal api types [\#52](https://github.com/theolind/pymysensors/pull/52) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update pyserial to version 3.1.1 [\#50](https://github.com/theolind/pymysensors/pull/50) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add MQTT client Gateway layer [\#49](https://github.com/theolind/pymysensors/pull/49) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update handle\_req to return zero values [\#48](https://github.com/theolind/pymysensors/pull/48) ([mch3000](https://github.com/mch3000))
- Handle heartbeat message [\#46](https://github.com/theolind/pymysensors/pull/46) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add class for testing protocol\_version 1.5 [\#45](https://github.com/theolind/pymysensors/pull/45) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add const for mysensors 2.0 [\#44](https://github.com/theolind/pymysensors/pull/44) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Bump version to 0.7.dev0 [\#43](https://github.com/theolind/pymysensors/pull/43) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.6](https://github.com/theolind/pymysensors/tree/0.6) (2016-04-19)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.5...0.6)

**Closed issues:**

- Error on loading of sensors JSON after inpropper shutdown [\#40](https://github.com/theolind/pymysensors/issues/40)
- Parse error on gateway startup [\#17](https://github.com/theolind/pymysensors/issues/17)
- Crash when a node has already ID but gateway doesn't know it [\#10](https://github.com/theolind/pymysensors/issues/10)
- Problems seeing node mysensor data on home assistant dashboard using mysensors.py [\#7](https://github.com/theolind/pymysensors/issues/7)

**Merged pull requests:**

- 0.6 [\#42](https://github.com/theolind/pymysensors/pull/42) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add safe saving and loading of persistence file [\#41](https://github.com/theolind/pymysensors/pull/41) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Move except statements upstream [\#39](https://github.com/theolind/pymysensors/pull/39) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Handle error for unknown node during presentation [\#38](https://github.com/theolind/pymysensors/pull/38) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add test env, local and travis [\#36](https://github.com/theolind/pymysensors/pull/36) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Update readme and main.py [\#35](https://github.com/theolind/pymysensors/pull/35) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add protocol\_version to json encoder [\#34](https://github.com/theolind/pymysensors/pull/34) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Rename tests/test.py to tests/test\_mysensors.py [\#33](https://github.com/theolind/pymysensors/pull/33) ([MartinHjelmare](https://github.com/MartinHjelmare))
- don't let exceptions in event callback bubble up into library. [\#32](https://github.com/theolind/pymysensors/pull/32) ([Br3nda](https://github.com/Br3nda))
- Travis [\#31](https://github.com/theolind/pymysensors/pull/31) ([Br3nda](https://github.com/Br3nda))
- Add TCP ethernet gateway [\#28](https://github.com/theolind/pymysensors/pull/28) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.5](https://github.com/theolind/pymysensors/tree/0.5) (2016-02-12)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.4...0.5)

**Closed issues:**

- Unable to send message to actuator without delay between each char, Arduino Pro Mini 3.3 V [\#21](https://github.com/theolind/pymysensors/issues/21)

**Merged pull requests:**

- Version 0.5 [\#27](https://github.com/theolind/pymysensors/pull/27) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix add\_child\_sensor [\#26](https://github.com/theolind/pymysensors/pull/26) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix some PEP issues. [\#25](https://github.com/theolind/pymysensors/pull/25) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Handling message-type req [\#24](https://github.com/theolind/pymysensors/pull/24) ([forsberg](https://github.com/forsberg))
- Add kwargs to set\_child\_value functions [\#23](https://github.com/theolind/pymysensors/pull/23) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix PEP issues [\#20](https://github.com/theolind/pymysensors/pull/20) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Remove sleep in connect function [\#19](https://github.com/theolind/pymysensors/pull/19) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Add threading.lock for send function [\#16](https://github.com/theolind/pymysensors/pull/16) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix decode partial data [\#15](https://github.com/theolind/pymysensors/pull/15) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.4](https://github.com/theolind/pymysensors/tree/0.4) (2016-01-07)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.3...0.4)

**Merged pull requests:**

- Version 0.4 [\#14](https://github.com/theolind/pymysensors/pull/14) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fifo queue, implementing switches [\#13](https://github.com/theolind/pymysensors/pull/13) ([MartinHjelmare](https://github.com/MartinHjelmare))
- Fix attributes [\#11](https://github.com/theolind/pymysensors/pull/11) ([MartinHjelmare](https://github.com/MartinHjelmare))

## [0.3](https://github.com/theolind/pymysensors/tree/0.3) (2015-10-09)
[Full Changelog](https://github.com/theolind/pymysensors/compare/0.2...0.3)

**Closed issues:**

- Install error on Home Assistant. [\#5](https://github.com/theolind/pymysensors/issues/5)

**Merged pull requests:**

- Bump the version number to 0.3. [\#9](https://github.com/theolind/pymysensors/pull/9) ([andythigpen](https://github.com/andythigpen))
- Pass protocol version through from SerialGateway to Gateway. [\#8](https://github.com/theolind/pymysensors/pull/8) ([andythigpen](https://github.com/andythigpen))

## [0.2](https://github.com/theolind/pymysensors/tree/0.2) (2015-08-15)
**Merged pull requests:**

- Add setup.py [\#4](https://github.com/theolind/pymysensors/pull/4) ([balloob](https://github.com/balloob))
- Fix ValueError issue when decoding a message. [\#2](https://github.com/theolind/pymysensors/pull/2) ([andythigpen](https://github.com/andythigpen))
- Improvements [\#1](https://github.com/theolind/pymysensors/pull/1) ([andythigpen](https://github.com/andythigpen))



\* *This Change Log was automatically generated by [github_changelog_generator](https://github.com/skywinder/Github-Changelog-Generator)*