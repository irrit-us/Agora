# Action log：`go test` 逐条枚举
实验与 [`generate_experiment_stats.py`](agent/scripts/generate_experiment_stats.py) 中 SESSIONS 对应。
规则：日志行匹配 `[TOOL CALL] run_command:` 且命令中含 `go test`（大小写不敏感）。

## go-ethereum / GPT 5.2
文件：`agent/data/test_history/go-ethereum/action_logs/session_20260327_223400.log`
**条数：73**
1. `go test ./core/vm -run TestPhantomLengthModExp_IntCastCrashOnOversizedLengthWords -count=1`
2. `go test ./eth/catalyst -run TestForkchoiceFinalityMismatchPoisoningCausesPermanentBadBlockAndHeadDivergence -count=1`
3. `go test ./eth/catalyst -run TestForkchoiceFinalityMismatchPoisoningCausesPermanentBadBlockAndHeadDivergence -count=1`
4. `go test ./eth/catalyst -run TestCrashTornBlockWriteCausesEngineToReturnVALIDWithoutState -count=1`
5. `go test ./eth/catalyst -run TestCrashTornBlockWriteCausesEngineToReturnVALIDWithoutState -count=1`
6. `go test ./eth/catalyst -run TestCrashTornInvalidBlockLaunderedIntoVALIDAndCanonical -count=1`
7. `go test ./eth/catalyst -run TestCrashTornInvalidBlockLaunderedIntoVALIDAndCanonical -count=1`
8. `go test ./eth/catalyst -run TestReorgAwayFromPhantomHeadCorruptsCanonicalMapping -count=1`
9. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
10. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
11. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
12. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
13. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
14. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
15. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
16. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
17. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
18. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
19. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
20. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
21. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
22. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
23. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
24. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
25. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
26. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
27. `go test ./eth/catalyst -run TestCrashTornBlockWriteCausesEngineToReturnVALIDWithoutState -count=1`
28. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
29. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
30. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
31. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
32. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
33. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
34. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
35. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
36. `go test ./eth/catalyst -count=1`
37. `go test ./eth/catalyst -list Test | head`
38. `go test ./eth/catalyst -run TestPhantomHeadAllowsWithdrawalPayloadBuildWithBogusStateRoot -count=1`
39. `go test ./eth/catalyst -run TestPhantomHeadAllowsWithdrawalPayloadBuildWithBogusStateRoot -count=1`
40. `go test ./eth/catalyst -count=1`
41. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
42. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
43. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
44. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
45. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
46. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
47. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
48. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
49. `go test ./eth/catalyst -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes -count=1`
50. `go test ./eth/catalyst -run TestFinalityAnchorBadBlockPoisoningCausesPermanentELDesync -count=1`
51. `go test ./eth/catalyst -run TestFinalityAnchorBadBlockPoisoningCausesPermanentELDesync -count=1`
52. `go test ./eth/catalyst -run TestSiblingPayloadRejectedDueToOverbroadInvalidCacheScope -count=1`
53. `go test ./eth/catalyst -run TestSiblingPayloadRejectedDueToOverbroadInvalidCacheScope -count=1`
54. `go test ./eth/catalyst -run TestContextCanceledNewPayloadMisclassifiedAsINVALID_PoisonsBadBlockCache -count=1`
55. `go test ./eth/catalyst -run TestContextCanceledNewPayloadMisclassifiedAsINVALID_PoisonsBadBlockCache -count=1`
56. `go test ./core -run TestP2PImportTransientMissingStateMisclassifiedAsBadBlock_PermanentSyncStall -count=1`
57. `go test ./core -run TestP2PImportTransientMissingStateMisclassifiedAsBadBlock_PermanentSyncStall -count=1`
58. `go test ./core -run TestP2PImportTransientMissingStateMisclassifiedAsBadBlock_PermanentSyncStall -count=1`
59. `go test ./core -run TestP2PImportTransientMissingStateMisclassifiedAsBadBlock_PermanentSyncStall -count=1`
60. `go test ./core -run TestP2PImportTransientMissingStateMisclassifiedAsBadBlock_PermanentSyncStall -count=1 -v`
61. `go test ./eth/catalyst -run TestForkchoiceSetHeadOnUnexecutedBlock_MissingStateMustNotBeMisclassifiedAsINVALID -count=1`
62. `go test ./core -run TestP2PImportTransientMissingStateMisclassifiedAsBadBlock_PermanentSyncStall -count=1`
63. `go test ./core -run TestP2PImportTransientMissingStateMisclassifiedAsBadBlock_PermanentSyncStall -count=1 -v`
64. `go test ./eth/catalyst -run TestForkchoiceFinalityMismatchPoisoningCausesPermanentBadBlockAndHeadDivergence -count=1 -v`
65. `go test ./eth/catalyst -run TestCrashTornInvalidBlockLaunderedIntoVALIDAndCanonical -count=1`
66. `go test ./eth/catalyst -run TestPayloadIDCollisionAcrossSiblingHeadsCausesCrossForkPayloadConfusion -count=1`
67. `go test ./eth/catalyst -run TestPayloadIDCollisionAcrossSiblingHeadsCausesCrossForkPayloadConfusion -count=1`
68. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
69. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1`
70. `go test ./eth/catalyst -run TestPhantomFinalizedAnchorPinsNodeToUnexecutableChain -count=1 -v`
71. `go test ./eth/catalyst -run TestForkchoiceFinalityMismatchPoisoningCausesPermanentBadBlockAndHeadDivergence -count=1`
72. `go test ./eth/catalyst -run TestVersionedHashMismatchBadBlockPoisoningPersistsAndRejectsLaterValidPayload -count=1`
73. `go test ./eth/catalyst -run TestVersionedHashMismatchBadBlockPoisoningPersistsAndRejectsLaterValidPayload -count=1`

## go-ethereum / Claude Sonnet 4.5
文件：`agent/data/test_history/go-ethereum/action_logs/session_20260328_133256.log`
**条数：89**
1. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s`
2. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | head -100`
3. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | head -150`
4. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1`
5. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | grep -A 5 "INVALID"`
6. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | head -50`
7. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | grep "validation error"`
8. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | head -50`
9. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | head -60`
10. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1`
11. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1`
12. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1`
13. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | head -20`
14. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | head -20`
15. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1 | head -30`
16. `cd /root && go test -v -run TestEth2PrepareAndGetPayload ./eth/catalyst/ -timeout 10s 2>&1 | head -5`
17. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1`
18. `cd /root && go test -v -run TestTerminalBlockFinalityConfusionViaSelectiveTTDAnnouncement ./eth/catalyst/ -timeout 60s 2>&1`
19. `cd /root && go test -v ./eth/catalyst -run TestByzantineFinalizationEquivocationViaConflictingForkchoiceUpdated -timeout 60s`
20. `cd /root && go test -v ./eth/catalyst -run TestByzantineFinalizationEquivocationViaConflictingForkchoiceUpdated -timeout 60s`
21. `cd /root && go test -v ./eth/catalyst -run TestByzantineFinalizationEquivocationViaConflictingForkchoiceUpdated -timeout 60s 2>&1 | grep -A 2 "Step 3\|BUG:"`
22. `cd /root && go test -v ./eth/catalyst -run TestByzantineFinalizationEquivocationViaConflictingForkchoiceUpdated -timeout 60s 2>&1 | tail -40`
23. `cd /root && go test -v ./eth/catalyst -run TestByzantineFinalizationEquivocationViaConflictingForkchoiceUpdated -timeout 60s 2>&1`
24. `cd /root && go test -v ./eth/catalyst -run TestByzantineFinalizationEquivocationViaConflictingForkchoiceUpdated -timeout 60s 2>&1 | tail -20`
25. `cd /root && go test -v -run TestByzantineSafeBlockEquivocationViaConflictingForkHeads ./eth/catalyst/`
26. `cd /root && go test -v -run TestByzantineSafeBlockEquivocationViaConflictingForkHeads ./eth/catalyst/ 2>&1 | head -100`
27. `cd /root && go test -v -run TestByzantineSafeBlockEquivocationViaConflictingForkHeads ./eth/catalyst/ 2>&1`
28. `cd /root && go test -v -run TestByzantineSafeBlockEquivocationViaConflictingForkHeads ./eth/catalyst/ 2>&1 | tail -20`
29. `cd /root && go test -run TestByzantineSafeBlockEquivocationViaConflictingForkHeads ./eth/catalyst/ 2>&1 | grep -E "(PASS|FAIL|BUG|INVARIANT)"`
30. `cd /root && go test -v -run TestByzantineHeadFinalityAnchoringViolationViaConflictingForkHead ./eth/catalyst -timeout 60s`
31. `cd /root && go test -v -run TestByzantineHeadFinalityAnchoringViolationViaConflictingForkHead ./eth/catalyst -timeout 60s 2>&1 | head -100`
32. `cd /root && go test -v -run TestByzantineHeadFinalityAnchoringViolationViaConflictingForkHead ./eth/catalyst -timeout 60s 2>&1`
33. `cd /root && go test -v -run TestByzantineHeadFinalityAnchoringViolationViaConflictingForkHead ./eth/catalyst -timeout 60s 2>&1 | tail -20`
34. `cd /root && go test -v -run TestByzantineHeadFinalityAnchoringViolationViaConflictingForkHead ./eth/catalyst -timeout 60s 2>&1 | grep -A2 "Step 3:"`
35. `cd /root && go test -v -run TestByzantineHeadFinalityAnchoringViolationViaConflictingForkHead ./eth/catalyst -timeout 60s 2>&1`
36. `cd /root && go test -v -run TestByzantineHeadFinalityAnchoringViolationViaConflictingForkHead ./eth/catalyst -timeout 60s 2>&1 | tail -15`
37. `cd /root && go test -run TestByzantineHeadFinalityAnchoringViolationViaConflictingForkHead ./eth/catalyst -timeout 60s 2>&1 | grep -E "(BUG:|INVARIANT VIOLATION:|Step [0-9]:)"`
38. `cd /root && go test -v -run TestByzantineFinalityHeightRegressionViaBackwardsForkFinalization ./eth/catalyst/`
39. `cd /root && go test -v -run TestByzantineFinalityHeightRegressionViaBackwardsForkFinalization ./eth/catalyst/ 2>&1`
40. `cd /root && go test -v -run TestByzantineFinalityHeightRegressionViaBackwardsForkFinalization ./eth/catalyst/ 2>&1 | tail -20`
41. `cd /root && go test -v -run TestByzantineFinalityHeightRegressionViaBackwardsForkFinalization ./eth/catalyst/ 2>&1`
42. `cd /root && go test -v -run TestByzantineFinalityHeightRegressionViaBackwardsForkFinalization ./eth/catalyst/ 2>&1 | tail -25`
43. `cd /tmp/geth-test && go test -v -run TestByzantineFinalityCascadeViaAlternatingForkFinalization ./eth/catalyst/`
44. `cd /tmp/geth-test 2>/dev/null || cd . && go test -v -run TestByzantineFinalityCascadeViaAlternatingForkFinalization ./eth/catalyst/ 2>&1 | head -100`
45. `cd /tmp/geth-test 2>/dev/null || cd . && go test -v -run TestByzantineFinalityCascadeViaAlternatingForkFinalization ./eth/catalyst/ 2>&1`
46. `cd /tmp/geth-test 2>/dev/null || cd . && go test -v -run TestByzantineFinalityCascadeViaAlternatingForkFinalization ./eth/catalyst/ 2>&1 | tail -50`
47. `cd /tmp/geth-test 2>/dev/null || cd . && go test -v -run TestByzantineFinalityCascadeViaAlternatingForkFinalization ./eth/catalyst/ 2>&1 | grep -A 20 "Finality Set Consistency"`
48. `cd /tmp/geth-test 2>/dev/null || cd . && go test -run TestByzantineFinalityCascadeViaAlternatingForkFinalization ./eth/catalyst/ 2>&1 | tail -3`
49. `cd /tmp/geth-test && go test -v -run TestByzantineSafeFinalizedForkDivergenceViaAncestryViolation ./eth/catalyst/`
50. `cd /tmp/geth-test && go test -v -run TestByzantineSafeFinalizedForkDivergenceViaAncestryViolation ./eth/catalyst/`
51. `cd /tmp/geth-test && go test -v -run TestByzantineSafeFinalizedForkDivergenceViaAncestryViolation ./eth/catalyst/`
52. `cd /root && go test -v -run TestByzantineSafeBlockLeapAttackNonMonotonicProgression ./eth/catalyst/ -timeout 60s`
53. `cd /root && go test -v -run TestByzantineSafeBlockLeapAttackNonMonotonicProgression ./eth/catalyst/ -timeout 60s`
54. `cd /root && go test -v -run TestByzantineSafeBlockLeapAttackNonMonotonicProgression ./eth/catalyst/ -timeout 60s`
55. `cd /root && go test -run TestByzantineSafeBlockLeapAttackNonMonotonicProgression ./eth/catalyst/ -timeout 60s 2>&1 | tail -30`
56. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s`
57. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s 2>&1 | head -200`
58. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s 2>&1`
59. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s 2>&1`
60. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s 2>&1 | grep -A 5 "Final block not"`
61. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s 2>&1`
62. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s 2>&1 | tail -100`
63. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s 2>&1 | grep -E "(ASSERTION|✓|⚠|FAIL|PASS)"`
64. `cd /root && go test -v -run TestByzantineFinalizedBlockLeapAttack ./eth/catalyst/ -timeout 60s 2>&1 | grep -A 2 "After fork switch"`
65. `cd eth/catalyst && go test -v -run TestByzantineSafeBlockBackwardHeightMovementAttack -timeout 60s`
66. `cd eth/catalyst && go test -v -run TestByzantineSafeBlockBackwardHeightMovementAttack -timeout 60s`
67. `cd eth/catalyst && go test -v -run TestByzantineSafeBlockBackwardHeightMovementAttack -timeout 60s 2>&1 | tail -50`
68. `cd eth/catalyst && go test -v -run TestByzantineSafeBlockBackwardHeightMovementAttack -timeout 60s 2>&1 | grep -A 20 "FINAL STATE"`
69. `cd eth/catalyst && go test -v -run TestByzantineSafeBlockCrossForkInconsistency -timeout 60s`
70. `cd /tmp/geth-test && go test -v -run TestByzantineSafeBlockLeapWithHeadRegressionInvalidAncestor ./eth/catalyst/ -timeout 5m`
71. `cd /tmp/geth-test && go test -v -run TestByzantineSafeBlockLeapWithHeadRegressionInvalidAncestor ./eth/catalyst/ -timeout 5m 2>&1`
72. `cd /tmp/geth-test && go test -v -run TestByzantineSafeBlockLeapWithHeadRegressionInvalidAncestor ./eth/catalyst/ -timeout 5m 2>&1 | head -50`
73. `cd /tmp/geth-test && go test -v -run TestByzantineSafeBlockLeapWithHeadRegressionInvalidAncestor ./eth/catalyst/ -timeout 5m 2>&1`
74. `cd /tmp/geth-test && go test -v -run TestByzantineSafeBlockLeapWithHeadRegressionInvalidAncestor ./eth/catalyst/ -timeout 5m 2>&1 | tail -20`
75. `cd /root && go test -v ./eth/catalyst -run TestByzantineSafeBlockOrphaningThroughGapRegionForking -timeout 60s`
76. `cd /root && go test -v ./eth/catalyst -run TestByzantineSafeBlockOrphaningThroughGapRegionForking -timeout 60s 2>&1 | head -200`
77. `cd /root && go test -v ./eth/catalyst -run TestByzantineSafeBlockOrphaningThroughGapRegionForking -timeout 60s 2>&1`
78. `cd /root && go test -v ./eth/catalyst -run TestByzantineSafeBlockOrphaningThroughGapRegionForking -timeout 60s 2>&1 | tail -100`
79. `cd /root && go test -v ./eth/catalyst -run TestByzantineSafeBlockOrphaningThroughGapRegionForking -timeout 60s 2>&1 | grep -A 200 "After fork switch"`
80. `cd /root && go test ./eth/catalyst -run TestByzantineSafeBlockOrphaningThroughGapRegionForking -timeout 60s 2>&1 | grep -E "(FAIL|PASS|ASSERTION)"`
81. `cd eth/catalyst && go test -v -run TestByzantineFinalizedSafeBlockInversionAttack -timeout 60s`
82. `cd eth/catalyst && go test -v -run TestByzantineFinalizedSafeBlockInversionAttack -timeout 60s`
83. `cd eth/catalyst && go test -v -run TestByzantineFinalizedSafeBlockInversionAttack -timeout 60s 2>&1 | tail -30`
84. `cd /tmp/geth-test && go test -v -run TestByzantineCrossForkPointerInjectionAttack ./eth/catalyst/ -timeout 30s`
85. `cd /tmp/geth-test && go test -v -run TestByzantineCrossForkPointerInjectionAttack ./eth/catalyst/ -timeout 30s 2>&1`
86. `cd eth/catalyst && go test -v -run TestByzantineFinalizedBlockRollbackAttack -timeout 60s`
87. `cd eth/catalyst && go test -v -run TestByzantineFinalizedBlockRollbackAttack -timeout 60s 2>&1 | tail -50`
88. `cd eth/catalyst && go test -run TestByzantineFinalizedBlockRollbackAttack -timeout 60s 2>&1 | grep -A 20 "Building competing fork"`
89. `cd eth/catalyst && go test -run TestByzantineFinalizedBlockRollbackAttack -timeout 60s 2>&1`

## go-ethereum / Gemini 3.1 Pro
文件：`agent/data/test_history/go-ethereum/action_logs/session_20260328_105651.log`
**条数：8**
1. `go test -v -run TestTransientStateGapMisclassifiedAsINVALIDPoisonsForkchoiceAndSplitsELNodes ./eth/catalyst`
2. `cd eth/catalyst && go test -run TestCrashLoopViaOrphanedFinalizedBlock`
3. `cd eth/catalyst && go test -v -run TestCrashLoopViaOrphanedFinalizedBlock`
4. `go test -v ./eth/catalyst -run TestStateDatabaseCorruptionViaPrunedAncestorRollback`
5. `go test -v ./eth/catalyst -run TestStateDatabaseCorruptionViaPrunedAncestorRollback`
6. `go test -v ./eth/catalyst -run TestStateDatabaseCorruptionViaPrunedAncestorRollback`
7. `go test -v ./eth/catalyst -run TestStateDatabaseCorruptionViaPrunedAncestorRollback`
8. `go test -v ./eth/catalyst -run TestStateDatabaseCorruptionViaPrunedAncestorRollback`

## avalanchego / GPT 5.2
文件：`agent/data/test_history/avalanchego/action_logs/session_20260327_223344.log`
**条数：36**
1. `go test ./snow/engine/snowman -run TestEngineDoubleChit -count=1`
2. `go test ./snow/engine/snowman -run TestEngineDoubleChit -count=1 -v`
3. `go test ./snow/engine/snowman -run TestCrashRestartRequestIDReuseDropsStaleChits -count=1`
4. `go test ./snow/engine/snowman -run TestInFlightValidatorWeightShiftBreaksPollDeterminismAndYieldsConflictingSnowmanAccepts -count=1`
5. `go test ./snow/engine/snowman -run TestCrashRestartRequestIDReuseDropsStaleChits -count=1`
6. `go test ./snow/engine/snowman -run TestInFlightValidatorWeightShiftBreaksPollDeterminismAndYieldsConflictingSnowmanAccepts -count=1`
7. `go test ./... -run '^TestEngineDoubleChit$' -count=1`
8. `go test ./snow/engine/snowman -run '^TestEngineDoubleChit$' -count=1`
9. `go test ./... -run TestEngineDoubleChit -count=1`
10. `go test ./snow/engine/snowman -run TestEngineDoubleChit -count=1`
11. `go test ./snow/engine/snowman -run TestNonVoterChitInjectionLetsNonValidatorsSteerPollAndForkHonestEngines -count=1`
12. `go test ./snow/engine/snowman -run TestCrashRestartRequestIDReuseDropsStaleChits -count=1`
13. `go test ./snow/engine/snowman -run TestEngineDoubleChit -count=1`
14. `go test ./snow/consensus/snowman -run TestStrategicConfidenceManipulation -count=1`
15. `go test ./snow/engine/snowman -run TestTwinChitSplitVoteViaInconsistentPreferredAcceptedIDsCausesDivergentFinalization -count=1`
16. `go test ./snow/engine/snowman -run TestTwinChitSplitVoteViaInconsistentPreferredAcceptedIDsCausesDivergentFinalization -count=1`
17. `go test ./snow/engine/snowman -run TestTwinChitSplitVoteViaInconsistentPreferredAcceptedIDsCausesDivergentFinalization -count=1`
18. `go test ./snow/engine/snowman -run TestTwinChitSplitVoteViaInconsistentPreferredAcceptedIDsCausesDivergentFinalization -count=1`
19. `go test ./snow/engine/snowman -count=1`
20. `go test ./snow/engine/snowman -run TestCrashRestartRequestIDReuseDropsStaleChits -count=1`
21. `go test ./snow/engine/snowman -run TestCrossTypeResponseInjectionDoubleCountsValidatorAndPrematurelyAcceptsBlock -count=1`
22. `go test ./snow/engine/snowman -run TestCrashRestartRequestIDReuseDropsStaleChits -count=1`
23. `go test ./snow/engine/snowman -run TestCrossTypeResponseInjectionDoubleCountsValidatorAndPrematurelyAcceptsBlock -count=1`
24. `go test ./snow/engine/snowman -run TestNonVoterChitInjectionLetsNonValidatorsSteerPollAndForkHonestEngines -count=1`
25. `go test ./snow/engine/snowman -run TestCrashRestartRequestIDReuseDropsStaleChits -count=1`
26. `go test ./snow/engine/snowman -run Test -count=1`
27. `go test ./snow/engine/snowman/bootstrap -run TestGappedAncestorsResponse_ClearsOutstandingFetch_OrphanBlockNeverRefetched -count=1`
28. `go test ./snow/engine/snowman -run TestGappedAncestorsResponse -count=1`
29. `go test ./snow/engine/snowman -run TestCrashRestartRequestIDReuseDropsStaleChits -count=1`
30. `go test ./... -run TestTwinChitSplitVoteViaInconsistentPreferredAcceptedIDsCausesDivergentFinalization -count=1`
31. `go test ./snow/engine/snowman -run TestTwinChitSplitVoteViaInconsistentPreferredAcceptedIDsCausesDivergentFinalization -count=1`
32. `go test ./snow/engine/snowman -run ^TestEngineDoubleChit$ -count=1`
33. `go test ./snow/engine/snowman -run ^TestEngineDoubleChit$ -count=1 -v`
34. `go test ./snow/engine/snowman -run TestNonVoterChitInjectionLetsNonValidatorsSteerPollAndForkHonestEngines -count=1`
35. `go test ./snow/engine/snowman -run TestCrashRestartRequestIDReuseDropsStaleChits -count=1`
36. `go test ./snow/engine/snowman -run TestMixedTerminalResponseConfusion_ChitsThenQueryFailedDoubleRemovesPollEntry -count=1`

## avalanchego / Claude Sonnet 4.5
文件：`agent/data/test_history/avalanchego/action_logs/session_20260328_133250.log`
**条数：98**
1. `cd snow/engine/snowman && go test -v -run TestByzantineSelectiveResponseInducingDivergentConfidenceAndConflictingCommits`
2. `cd snow/engine/snowman && go test -v -run TestByzantineSelectiveResponseInducingDivergentConfidenceAndConflictingCommits 2>&1`
3. `cd snow/engine/snowman && go test -v -run TestByzantineSelectiveResponseInducingDivergentConfidenceAndConflictingCommits 2>&1`
4. `cd snow/engine/snowman && go test -v -run TestByzantineSelectiveResponseInducingDivergentConfidenceAndConflictingCommits 2>&1`
5. `cd snow/engine/snowman && go test -v -run TestByzantineSelectiveResponseInducingDivergentConfidenceAndConflictingCommits 2>&1`
6. `cd snow/engine/snowman && go test -v -run TestCascadingChainDivergenceThroughSustainedSelectiveByzantineResponses -timeout 30s`
7. `cd snow/engine/snowman && go test -v -run TestCascadingChainDivergenceThroughSustainedSelectiveByzantineResponses -timeout 30s`
8. `cd snow/engine/snowman && go test -v -run TestCascadingChainDivergenceThroughSustainedSelectiveByzantineResponses -timeout 30s 2>&1 | tail -50`
9. `cd snow/engine/snowman && go test -run TestCascadingChainDivergenceThroughSustainedSelectiveByzantineResponses -timeout 30s 2>&1 | grep -A 20 "Final Verification"`
10. `cd snow/engine/snowman && go test -run TestCascadingChainDivergenceThroughSustainedSelectiveByzantineResponses -timeout 30s 2>&1 | grep -E "(Height [0-9] finalized|Final Verification|SAFETY VIOLATION)" | head -20`
11. `cd snow/engine/snowman && go test -run TestCascadingChainDivergenceThroughSustainedSelectiveByzantineResponses -timeout 30s 2>&1 | grep -E "(Error|FAIL)" | head -5`
12. `cd snow/engine/snowman && go test -run TestCascadingChainDivergenceThroughSustainedSelectiveByzantineResponses -timeout 30s 2>&1 | tail -100 | head -80`
13. `cd snow/engine/snowman && go test -v -run TestConfidenceOscillationViaIntermittentByzantineWithholdingLeadingToOffsetFinalization -timeout 30s`
14. `cd snow/engine/snowman && go test -v -run TestConfidenceOscillationViaIntermittentByzantineWithholdingLeadingToOffsetFinalization -timeout 30s 2>&1`
15. `cd snow/engine/snowman && go test -v -run TestConfidenceOscillationViaIntermittentByzantineWithholdingLeadingToOffsetFinalization -timeout 30s 2>&1 | tail -50`
16. `cd snow/engine/snowman && go test -v -run TestConfidenceOscillationViaIntermittentByzantineWithholdingLeadingToOffsetFinalization -timeout 30s 2>&1 | tail -20`
17. `cd snow/engine/snowman && go test -v -run TestTransitiveConfidencePoisoningViaSelectiveDAGExposure -timeout 30s`
18. `cd snow/engine/snowman && go test -run TestTransitiveConfidencePoisoningViaSelectiveDAGExposure -timeout 30s 2>&1 | tail -20`
19. `cd /root && go test -v -run TestConfidenceAmplificationViaResponseDuplication ./snow/engine/snowman/ -timeout 30s`
20. `cd snow/engine/snowman && go test -v -run TestRecoveryPhaseExploitationOfPreExistingByzantineInducedDivergence -timeout 30s`
21. `cd snow/engine/snowman && go test -v -run TestRecoveryPhaseExploitationOfPreExistingByzantineInducedDivergence -timeout 30s`
22. `cd snow/engine/snowman && go test -v -run TestRecoveryPhaseExploitationOfPreExistingByzantineInducedDivergence -timeout 30s`
23. `cd snow/engine/snowman && go test -v -run TestRecoveryPhaseExploitationOfPreExistingByzantineInducedDivergence -timeout 30s`
24. `cd snow/engine/snowman && go test -v -run TestByzantineStrategicAbstentionCausingPerpetualConfidenceStarvation -timeout 30s`
25. `cd snow/engine/snowman && go test -v -run TestByzantineStrategicAbstentionCausingPerpetualConfidenceStarvation -timeout 30s`
26. `cd snow/engine/snowman && go test -v -run TestByzantineStrategicAbstentionCausingPerpetualConfidenceStarvation -timeout 30s`
27. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceManipulationWithSelectiveEquivocationCausingSafetyViolation 2>&1 | head -100`
28. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceManipulationWithSelectiveEquivocationCausingSafetyViolation 2>&1 | tail -50`
29. `cd snow/engine/snowman && go test -run TestByzantineConfidenceManipulationWithSelectiveEquivocationCausingSafetyViolation 2>&1`
30. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceManipulationWithSelectiveEquivocationCausingSafetyViolation 2>&1 | grep -A 20 "Simplified Attack"`
31. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceManipulationWithSelectiveEquivocationCausingSafetyViolation 2>&1`
32. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceManipulationWithSelectiveEquivocationCausingSafetyViolation 2>&1`
33. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceManipulationWithSelectiveEquivocationCausingSafetyViolation 2>&1 | tail -20`
34. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidenceStarvationCausingChainDivergence -timeout 30s 2>&1 | head -100`
35. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidenceStarvationCausingChainDivergence -timeout 30s 2>&1`
36. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidenceStarvationCausingChainDivergence -timeout 30s 2>&1`
37. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidenceStarvationCausingChainDivergence -timeout 30s 2>&1`
38. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidenceStarvationCausingChainDivergence -timeout 30s 2>&1`
39. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidenceStarvationCausingChainDivergence -timeout 30s 2>&1`
40. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidenceStarvationCausingChainDivergence -timeout 30s 2>&1`
41. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidenceStarvationCausingChainDivergence -timeout 30s 2>&1`
42. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s`
43. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s`
44. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s 2>&1 | head -100`
45. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s 2>&1 | head -50`
46. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s 2>&1 | head -50`
47. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s 2>&1`
48. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s 2>&1`
49. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s 2>&1`
50. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineConfidenceGradientAttack -timeout 60s 2>&1`
51. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceDesynchronizationViaAsymmetricTimingCausingSafetyViolation -timeout 30s`
52. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceDesynchronizationViaAsymmetricTimingCausingSafetyViolation -timeout 30s 2>&1`
53. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceDesynchronizationViaAsymmetricTimingCausingSafetyViolation -timeout 30s 2>&1 | tail -20`
54. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceDesynchronizationViaAsymmetricTimingCausingSafetyViolation -timeout 30s 2>&1 | tail -25`
55. `cd snow/engine/snowman && go test -v -run TestByzantineConfidenceDesynchronizationViaAsymmetricTimingCausingSafetyViolation -timeout 30s 2>&1 | tail -30`
56. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineCoordinatedPreferenceReversalCausingConfidenceOscillationDeadlock -timeout 60s`
57. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineCoordinatedPreferenceReversalCausingConfidenceOscillationDeadlock -timeout 60s 2>&1 | head -100`
58. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineCoordinatedPreferenceReversalCausingConfidenceOscillationDeadlock -timeout 60s 2>&1`
59. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineCoordinatedPreferenceReversalCausingConfidenceOscillationDeadlock -timeout 60s 2>&1 | tail -80`
60. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineCoordinatedPreferenceReversalCausingConfidenceOscillationDeadlock -timeout 60s 2>&1 | grep -A 5 "PASS\|FAIL"`
61. `cd /root && go test -v ./snow/engine/snowman -run TestByzantineCoordinatedPreferenceReversalCausingConfidenceOscillationDeadlock -timeout 60s 2>&1 | grep -B 5 "Error Trace\|Test:"`
62. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/`
63. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | head -100`
64. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | tail -30`
65. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | grep -A2 "LastAccepted:"`
66. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | grep "BlockA ID:\|BlockB ID:\|LastAccepted:"`
67. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | grep "Round.*complete"`
68. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | grep "Round.*polls.Len\|Round.*blockA.*Status" | head -20`
69. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | grep -E "Round [0-9]+ complete|Round [0-9]+:.*polls.Len|Round [0-9]+:.*blockA.*Status" | head -30`
70. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | tail -80`
71. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | tail -100`
72. `cd /Users/shemol/avalanchego && go test -v -run TestByzantineLateStageConflictingBlockInjectionWithConfidencePoisoning ./snow/engine/snowman/ 2>&1 | grep -A50 "=== LIVENESS VIOLATION"`
73. `cd /root && go test -v -run TestByzantineSelectiveBlockRevelationForHonestNodeViewFragmentation ./snow/engine/snowman/ -timeout 30s`
74. `cd /root && go test -v -run TestByzantineSelectiveBlockRevelationForHonestNodeViewFragmentation ./snow/engine/snowman/ -timeout 30s 2>&1 | tail -50`
75. `cd /root && timeout 10 go test -v -run TestByzantineSelectiveBlockRevelationForHonestNodeViewFragmentation ./snow/engine/snowman/ 2>&1 | grep -A 20 "Final Assertions"`
76. `cd /root && timeout 10 go test -run TestByzantineSelectiveBlockRevelationForHonestNodeViewFragmentation ./snow/engine/snowman/ 2>&1`
77. `cd /root && go test -run TestByzantineSelectiveBlockRevelationForHonestNodeViewFragmentation ./snow/engine/snowman/ -timeout 10s 2>&1 | tail -100`
78. `cd /root && go test -run TestByzantineSelectiveBlockRevelationForHonestNodeViewFragmentation ./snow/engine/snowman/ -timeout 10s 2>&1 | grep -E "(FAIL|PASS|VIOLATION|Protocol Resistant)" | head -20`
79. `cd /root && go test -run TestByzantineSelectiveBlockRevelationForHonestNodeViewFragmentation ./snow/engine/snowman/ -timeout 10s 2>&1 | grep -A 5 "Final Assertions"`
80. `cd /root && go test -run TestByzantineSelectiveBlockRevelationForHonestNodeViewFragmentation ./snow/engine/snowman/ -timeout 10s 2>&1 | grep -A 2 "Block statuses"`
81. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidencePoisoningAttack -timeout 30s`
82. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidencePoisoningAttack -timeout 30s 2>&1`
83. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidencePoisoningAttack -timeout 30s 2>&1`
84. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidencePoisoningAttack -timeout 30s 2>&1 | tail -50`
85. `cd snow/engine/snowman && go test -run TestCascadingMultiHeightConfidencePoisoningAttack -timeout 30s 2>&1 | grep -A 30 "Final State Check"`
86. `cd snow/engine/snowman && timeout 30 go test -run TestCascadingMultiHeightConfidencePoisoningAttack 2>&1`
87. `cd snow/engine/snowman && go test -run TestCascadingMultiHeightConfidencePoisoningAttack -timeout 30s 2>&1 > /tmp/test_output.txt && tail -100 /tmp/test_output.txt`
88. `cd snow/engine/snowman && go test -v -run TestCascadingMultiHeightConfidencePoisoningAttack -timeout 30s 2>&1 > /tmp/test_output_verbose.txt && cat /tmp/test_output_verbose.txt`
89. `cd snow/engine/snowman && go test -v -run TestByzantineVoteEquivocationForHonestNodeConsensusFragmentation -timeout 30s`
90. `cd snow/engine/snowman && go test -v -run TestByzantineVoteEquivocationForHonestNodeConsensusFragmentation -timeout 30s`
91. `cd snow/engine/snowman && go test -run TestByzantineVoteEquivocationForHonestNodeConsensusFragmentation -timeout 30s 2>&1 | tail -30`
92. `cd snow/engine/snowman && go test -v -run TestByzantineVoteEquivocationForHonestNodeConsensusFragmentation -timeout 30s 2>&1 | grep -A 5 "After round"`
93. `cd snow/engine/snowman && go test -run TestByzantineVoteEquivocationForHonestNodeConsensusFragmentation -timeout 30s 2>&1`
94. `cd snow/engine/snowman && go test -v -run TestByzantineRetroactiveParentConflictAfterFinalization -timeout 30s`
95. `cd snow/engine/snowman && go test -v -run TestByzantineRetroactiveParentConflictAfterFinalization -timeout 30s 2>&1`
96. `cd snow/engine/snowman && go test -v -run TestByzantineRetroactiveParentConflictAfterFinalization -timeout 30s 2>&1 | tail -50`
97. `cd snow/engine/snowman && go test -run TestByzantineRetroactiveParentConflictAfterFinalization -timeout 30s 2>&1 | grep -A 20 "Assertion 4"`
98. `cd snow/engine/snowman && go test -run TestByzantineRetroactiveParentConflictAfterFinalization -timeout 30s 2>&1 | grep -E "(BlockB1|BlockA2|Assertion)" | head -20`

## avalanchego / Gemini 3.1 Pro
文件：`agent/data/test_history/avalanchego/action_logs/session_20260328_105746.log`
**条数：0**
