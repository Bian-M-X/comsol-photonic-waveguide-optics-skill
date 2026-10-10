# 2D Hadamard: from a locked mask to independently checked evidence

**2026-10-10：固定二值掩膜的 19 项独立 COMSOL 验证与 13 组收敛比较全部通过。**
本案例展示一个完整、可检查的工作流结果：五波长伴随优化、阈值实验、冻结掩膜、
八源模态读出、独立验算以及离散波长/数值条件验证。
模型是 **2D 体材料折射率替代模型**，不代表 220 nm SOI 三维器件、加工结果或实测量子过程层析。

**All 19 locked-mask validation runs and 13 convergence comparisons passed.**
The compact public bundle preserves the raw numerical response and original
provenance hashes. Its verifier checks **numerical self-consistency only**:
`native_receipts_reverified: false`. Fresh licensed COMSOL execution is required
to reproduce the native simulations.

![Frozen binary design](figures/design.png)

设计区为 1.3 × 1.3 µm，接入波导宽 400 nm；物理端口依次为左、下、上、右。
掩膜在 `y=x` 镜像约束下重建，阈值为 `0.4683617431984674`。
该阈值来自单独记录的人工符号括区间实验；这条已观测历史随后用于形成新版默认策略，
软件历史重放与实际阈值序列一致。**这里没有重新执行新版默认的一键端到端原生 campaign，
也不主张旧版默认策略的原生轨迹已被复现。** 冻结后没有继续优化或调阈值。

The design square is 1.3 × 1.3 µm, with 400 nm access guides. The mask was
obtained through a separately recorded manual sign-bracket experiment and then
frozen before qualification. That observed lineage informed the new default
policy, whose software history replay matches the observed threshold sequence.
No fresh one-command end-to-end native campaign using that new default was run;
the earlier default's native trajectory and a global optimum are not claimed.

![Receipt-bound center field preview](figures/field-linear.png)

1550 nm 中心点的线性场强显示来自原生求解输出，见
[预览来源记录 / preview provenance](figures/preview-provenance.json)。
图像在物理显示窗口内插值，裁掉 PML/背衬区域后按窗口峰值归一化。
它用于理解传播形态，不用于推断绝对入射功率、收敛或连续波段性能。
图像文件未经再次裁剪、调色或重采样。

The preview is copied unchanged from the receipt-bound center visualization.
Its display interpolation and peak normalization are visualization operations,
not additional physical validation.

![Seven discrete wavelength checks](figures/spectrum-discrete.png)

上图只画七个实际计算点，不连线、不插值：五个训练波长为
1520、1536.61、1550、1565、1580 nm；两个未参与调掩膜的保留波长为
1543.3、1572.3 nm。所有光谱点采用同一核心/包层网格 `0.02/0.08 µm`，
因此图中的 1550 nm 点对应 `mesh020`，与下表单独列出的 `0.025 µm` 名义中心点不同。
每个点是一次确定性配置求解，没有统计重复或置信区间。
空心蓝色标记与较小的橙色标记分别表示六态最小条件保真度和条件 Choi 重叠；两者几乎重合。

The seven points establish acceptance at these sampled wavelengths, not a
continuous-band guarantee. See the exact [source data](figures/spectrum-source-data.csv),
[plot provenance](figures/spectrum-provenance.json), [SVG](figures/spectrum-discrete.svg)
and [PDF](figures/spectrum-discrete.pdf).

| 指标 / Metric | 名义中心点 / Nominal center | 19 项验证中的最差值 / Worst of 19 | 冻结门限 / Gate |
|---|---:|---:|---:|
| 全逻辑输入最小目标吞吐 / Minimum throughput over all logical inputs | 0.9475064821 | 0.9246576286 | ≥ 0.9 |
| 六态最小条件保真度 / Minimum six-state conditional fidelity | 0.9999822474 | 0.9995299555 | ≥ 0.987 |
| 条件 Choi 重叠 / Conditional Choi overlap | 0.9999822822 | 0.9995300228 | ≥ 0.987 |
| 两个输入的输出功率比 / Both-input output power ratios | 1.01141 / 0.988718 | 0.9215083 … 1.0851774 | 0.9 … 1.1 |

精确中心值和每一次验证的完整报告在 [bundle.json](evidence/bundle.json) 中；
表格是显示精度下的摘要，以原始数据和脚本重算为准。

## What was checked / 验证内容

每次求解包含同一模型内的八个独立源：TM0 左/下/上/右，然后 TM1 左/下/上/右。
原始出射矩阵记为 `A`，原始入射矩阵记为 `B`，元素均保存为 `[real, imag]`。
不对 `A` 进行 `A B^-1` 修正、不拟合独立端口相位。
基准固定为实解析 TM0 中心为正、TM1 在正横向坐标侧为正、所有端口 `Thetap=0`；
仅使用已声明参考面长度的解析相位修正。

The frozen logical target is `U = [[1,i],[i,1]] / sqrt(2)`. With
`T = A[rows 3,4; columns 1,2]` in one-based indexing:

采用事先固定的输入/输出相位矩阵 `D = diag(1, -i)`，有 `D U D = H`，
其中 `H = [[1,1],[1,-1]] / sqrt(2)`。因此本例在该明确相位约定下等效于 Hadamard；
这些固定相位不是根据仿真结果拟合得到的器件补偿。

- `eta_all = sigma_min(T)^2`, minimizing output power over every normalized complex logical input.
- `F6` is the minimum of `|(U psi)† T psi|² / ||T psi||²` over `0, 1, +, −, +i, −i`.
- Conditional Choi overlap is `|Tr(U†T)|² / (2 Tr(T†T))`; this is not experimental process tomography.
- Split ratios are `|T[0,j]|² / |T[1,j]|²` for each logical basis input.
- Full observed `8 × 8` passivity uses `sigma_max(A) ≤ 1.005`; reciprocity uses `max|A − Aᵀ| ≤ 0.005`.
- Incoming normalization uses `||B − I||₂ ≤ 0.005`; the logical mirror residual is at most `0.005`.
- All eight source-conditioned signed interior surface flux sums must close within `0.005` of declared `1 W/m` incident power. Modal-versus-net-flux differences remain unresolved rather than being labelled absorption or loss.

十九项验证按冻结顺序覆盖中心网格细化、四个其他训练波长、四个波长的外域/边界变化、
两个波长的更强 PML、两个波长的投影面变化、三个非中心波长的进一步网格细化，最后检查两个保留波长。
十三组配对比较要求六态吞吐及 `eta_all` 的绝对变化 ≤ `0.005`，
`F6`/Choi 变化 ≤ `0.002`，两个分光比变化 ≤ `0.02`。
详细配置、顺序和比较关系保存在 bundle 中，并由 verifier 与冻结 recipe 指纹核对。

These are declared engineering gates, not tolerances attributed to a paper.
The analytic coverage check covers the bound Hz modes of this fixed 400 nm
slab; it does not establish general cross-section or continuum completeness.

## Verify or reproduce / 复核与重新求解

在安装了仓库运行时及 `inverse-design` 科学计算依赖的环境中，从仓库根目录运行：

```console
python docs/showcases/hadamard-2d/verify.py
python docs/showcases/hadamard-2d/plot_spectrum.py
```

Expected numerical result:

```json
{"numeric_self_consistency_pass": true,
 "full_numerical_suite_pass": true,
 "native_receipts_reverified": false,
 "native_execution_reproduced": false,
 "completed_numeric_runs": 20,
 "completed_convergence_pairs": 13}
```

该检查重新计算原始矩阵、入射归一化、符号通量和全部收敛比较。
缺少验证项、原始数值与报告不一致、掩膜哈希改变、放宽门限或顺序改变均不会取得完整数值 PASS。
`manifest.json` 是未签名的导出完整性清单，不能认证 COMSOL 运行的真实性。
原生边界标志、原始 receipt 和被省略文件的哈希只作为来源链接；公共 verifier 无法重新核验被省略的
MPH、完整控制台、场采样或编译类文件。它不会把紧凑导出伪装为新的原生执行 receipt。

For fresh native reproduction, use the original
[COMSOL example and licensed-run instructions](../../../examples/comsol-hadamard-inverse/README.md).
Replay the frozen mask, rather than expecting optimization to recover the same contour:

```python
# From the repository root: prepare exact center + 19 replay configurations.
import json
from pathlib import Path
bundle = json.loads(Path("docs/showcases/hadamard-2d/evidence/bundle.json").read_text())
configs = Path("NEW_REPLAY_CONFIGS")
configs.mkdir(exist_ok=False)
for run in bundle["runs"]:
    (configs / (run["name"] + ".json")).write_text(json.dumps(run["config"]))
```

Run each configuration with `examples/comsol-hadamard-inverse/run.py`, the
bundled `evidence/mask.json`, a **new** native output directory, eight processors,
and a declared timeout; then run the original `analyze.py`. For example:

```console
python examples/comsol-hadamard-inverse/run.py --config NEW_REPLAY_CONFIGS/selected_binary.json --mask docs/showcases/hadamard-2d/evidence/mask.json --output NEW_CENTER_RUN --solver-root YOUR_COMSOL_ROOT --processors 8 --timeout 1200 --execute
python examples/comsol-hadamard-inverse/analyze.py NEW_CENTER_RUN
```

Repeat for the exact 19 configurations in bundle order and apply the 13 frozen
`campaign.convergence` pairs. This requires COMSOL Wave Optics and Optimization
licenses. Replaying the locked design is separate from reproducing the earlier
optimization/search trajectory. No fresh native solver is invoked by the public
verifier or plotting script.

## Cost and provenance / 成本与来源

最终默认 `coherent` 目标的六个独立原生梯度检查也已通过：五个训练波长的一条方向，
以及中心波长的第二条方向；每项使用两个有限差分步长，共十二组比较。
最大相对误差为 `2.6857e-5`，原始比较值、固定配置和来源哈希见
[默认梯度链独立审计](evidence/startup-gradient-audit.json)。这些检查只验证指定初始密度下的
方向导数，不证明所有方向或优化收敛；额外编译 `29.1362 s`、batch `382.9108 s`，
与下表的设计、阈值和器件验证成本分开。该紧凑记录仍不包含原生重型文件或原始收据。

| 单独记录的类别 / Separate category | 工作量 / Observed work | 编译 / Compile (s) | Batch (s) |
|---|---|---:|---:|
| 父任务记录的选定优化链 / Parent-inventoried selected optimization lineage | 5 jobs; 206 band evaluations; 1030 nominal training frequency-state evaluations; 40 additional center driven states | 17.3772 | 4152.8320 |
| 已发生的先前阈值搜索 / Prior incurred threshold searches | 5 jobs; 40 driven states | 16.2941 | 192.1051 |
| 最终名义中心点 / Accepted nominal center | 1 job; 8 driven states | 3.4502 | 36.7775 |
| 独立固定掩膜验证 / Independent locked-mask qualification | 19 jobs; 152 driven states; zero new optimization or threshold-search jobs | 91.5722 | 948.9223 |

这些类别不能混成“总研发成本”。训练计数不包括伴随、Newton 或线性求解；batch 时间包含验证、
导出和保存，并非纯物理求解时间。更早失败的分支、梯度试验、beta8/beta16 掩膜筛选和读出恢复
仍有已发生但未逐项纳入此表的成本，不能当作零。两个先前阈值端点的分光比失败结果也保留在 bundle 中。
选定优化链成本来自父任务的 receipt/trace 库存，与此次独立原生验证明确区分。

The [bundle](evidence/bundle.json) preserves each run's original receipt and
artifact hashes, complete numerical report, signed flux and costs. The original
independent audit also checked all 317 frozen source files and prior inputs
unchanged, and confirmed the native worker was released. Relevant original
SHA-256 provenance links are:

| Original artifact | SHA-256 |
|---|---|
| Locked mask | `90bdfde4ff488e0e64b05933d9d9428ee6cc712d09a19f7f228b03b7ce3d4dc7` |
| Independent qualification report | `4560d8894028b6346509fa83e1ce5823cab6e414fe84280b4773305108b63435` |
| Independent completion audit | `1479a5ef20533a54da644e6bee3a7030ac33383b51cb6102620afebd01f6780b` |
| Completion-audit script | `b7fffd0627992d81628cfcf7c716fad04fa2c70efa39f4ef5e2b4e89f2c73240` |
| Frozen independent native driver | `5ec1c87bcb1c88f8f61318b256cb684ab909b7d0fdba23da2d17fbd93ed2269e` |

图像来源与数值来源分别记录。图表源数据、源代码、可编辑矢量文件和 QA 结果随案例提供。
这份公开包不含重型原生模型、完整控制台、原始场数组、编译类文件或本机绝对路径。
