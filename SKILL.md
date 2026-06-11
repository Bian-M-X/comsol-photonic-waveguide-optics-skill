---
name: photonic-waveguide-optics
description: Use when building, running, debugging, optimizing, or reporting COMSOL-based finite-element optical simulations for integrated photonic waveguides and on-chip optical devices, including straight/rib/strip waveguides, bends, tapers, splitters, directional couplers, MMI couplers, Y-branches, ring resonators, Bragg gratings, grating couplers, MZI/aMZI/LT-aMZI interferometers, sensors, modulators, wavelength sweeps, port-based wave-optics models, 2D effective-index approximations, 3D validation, Java API batch automation, and external parameter optimization workflows. Compatible with licensed third-party finite-element solver installations without bundling or redistributing proprietary software.
---

# Photonic Waveguide Optics

本 skill 面向通用片上光子器件仿真，特别是基于用户自有 licensed COMSOL Multiphysics 安装环境的 strip/rib waveguide、bend、taper、directional coupler、MMI、Y-branch、ring resonator、Bragg grating、grating coupler、MZI/aMZI/LT-aMZI、sensor、modulator、端口型频域模型、扫谱、Java API batch 自动化和外部参数优化。

核心目标不是“画出几何”，而是形成可复现证据链：

1. 文献参数与器件拓扑清楚。
2. 几何、材料、端口、边界、网格设置可审计。
3. 独立模块先校准，再装配完整器件。
4. 频域/扫谱结果能与理论指标或论文结果对照。
5. 输出模型、脚本、日志、CSV/TXT 数据、图像、报告和可继续优化的工件。

## Publication And Local-Data Guardrail

本仓库和 skill 名称刻意不包含第三方商业求解器商标。正文可在兼容性语境下提到 COMSOL 相关可执行文件名或 Java API 工作流，但不得暗示官方授权、赞助、背书或隶属关系。

发布到公共仓库前必须检查并移除：

- 本机绝对路径、用户名、用户主目录。
- license server、license file、access token、credential。
- 私有论文 PDF、厂商文档、官方示例模型、官方截图、logo。
- `.mph`、`.class`、`.log`、cache、临时 sweep 输出，除非确认可公开。
- 未公开项目名、合作方信息、未授权数据。

求解器位置必须通过参数或环境变量传入，不要写死作者机器路径。默认使用：

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\LicensedSolverRoot'
$env:PHOTONIC_SOLVER_PREFS = Join-Path $env:TEMP 'photonic-waveguide-solver\prefs'
$env:PHOTONIC_SOLVER_CONFIG = Join-Path $env:TEMP 'photonic-waveguide-solver\config'
$env:PHOTONIC_SOLVER_TMP = Join-Path $env:TEMP 'photonic-waveguide-solver\tmp'
```

`PHOTONIC_SOLVER_ROOT` 应指向包含以下相对路径的本地 licensed solver 根目录：

```text
bin\win64\comsolbatch.exe
java\win64\jre\bin\javac.exe
plugins\*.jar
```

## Reference Map

当任务需要深入细节时，按需读取 references，而不是一次性加载所有内容：

- `references/environment-and-runner.md`: 本地 solver root 配置、batch runner、runtime dirs、隐私安全 dry-run。
- `references/wave-optics-port-models.md`: 2D EIM、材料、ports、BMA、边界、dataset、mesh。
- `references/device-family-workflows.md`: 直波导、弯曲、taper、splitter、coupler、MMI、Y-branch、ring、Bragg、grating、sensor、modulator 等通用器件族流程。
- `references/interferometer-workflows.md`: MZI、aMZI、LT-aMZI 等干涉仪专用拓扑与验收。
- `references/optimization-and-reporting.md`: 参数扫描、能量诊断、优化、报告。
- `references/legal-and-trademark-notes.md`: 商标、许可、公开发布风险。

2026-06 扩展参考：
- `references/smooth-bend-geometry.md`: 解析圆弧/环形扇区弯曲、中心线长度守恒、真光滑弯曲与多段折线近似的比较方法。
- `references/subagent-orchestration.md`: 计划、几何、执行、代码审计、模型审计、结果审计、数据处理等 subagent 的分工与调用约束。
- `references/comsol-mcp-evaluation.md`: Java batch、mphserver/LiveLink、潜在 MCP server 桥接方案的优先级评估。
- `references/quantum-photonic-knowledge-base.md`: 面向片上量子光学仿真的基础器件、门、MZI 网格、验证指标和关键文献入口。
- `references/project-structure-and-git.md`: 新工程目录、命名、artifact 管理、git 仓库策略和交接规范。
- `references/source-notes.md`: 官方文档、MCP 规范和量子光学论文入口；开始新研究阶段前应刷新。

当任务明确要求 subagent、并行审计或 delegated simulation work 时，先读 `references/subagent-orchestration.md`，再只读取匹配的 `agents/*.md` 角色文件。subagent 默认不得接触许可证、私有 solver 路径、`.mph` 大文件或未脱敏日志，除非用户明确授权。

## 1. Environment And Execution

优先使用 Java API + batch 自动化：

1. 生成或修改 Java 源码。
2. 使用 solver bundled `javac.exe` 编译。
3. 使用 `comsolbatch.exe` 运行 `.class`。
4. 在 Java API 内保存 `.mph`。
5. 将关键指标打印到 stdout 或写入普通 CSV/TXT。
6. 用 Python/PowerShell 做数据整理、绘图和报告。

不优先使用：

- `mphserver` 作为第一路线，除非用户明确需要交互式服务。
- 独立 Java 直接 `ModelUtil.create(...)` 后脱离 batch 环境运行。
- solver-side Java 读取大量外部普通文本配置；如果确实需要配置，优先把小配置嵌入 Java 源码或由外层脚本生成源码。

可靠编译模式：

```powershell
$solverRoot = $env:PHOTONIC_SOLVER_ROOT
if (-not $solverRoot) { throw 'Set PHOTONIC_SOLVER_ROOT first.' }
$plugins = Join-Path $solverRoot 'plugins'
$javac = Join-Path $solverRoot 'java\win64\jre\bin\javac.exe'
$cp = (Get-ChildItem -LiteralPath $plugins -Filter '*.jar' | ForEach-Object { $_.FullName }) -join ';'
& $javac -proc:none -cp $cp 'C:\Path\To\ModelSource.java'
```

`-proc:none` 很重要，可避免注解处理相关噪声和失败。

可靠 batch 模式：

```powershell
$solverRoot = $env:PHOTONIC_SOLVER_ROOT
$prefs = if ($env:PHOTONIC_SOLVER_PREFS) { $env:PHOTONIC_SOLVER_PREFS } else { Join-Path $env:TEMP 'photonic-waveguide-solver\prefs' }
$cfg = if ($env:PHOTONIC_SOLVER_CONFIG) { $env:PHOTONIC_SOLVER_CONFIG } else { Join-Path $env:TEMP 'photonic-waveguide-solver\config' }
$tmp = if ($env:PHOTONIC_SOLVER_TMP) { $env:PHOTONIC_SOLVER_TMP } else { Join-Path $env:TEMP 'photonic-waveguide-solver\tmp' }
$batch = Join-Path $solverRoot 'bin\win64\comsolbatch.exe'
& $batch `
  -prefsdir $prefs `
  -configuration $cfg `
  -tmpdir $tmp `
  -inputfile 'C:\Path\To\ModelSource.class' `
  -outputfile 'C:\Path\To\OutputModel.mph' `
  -batchlog 'C:\Path\To\BatchLog.log'
```

同一组 runtime dirs 不要被多个 batch jobs 并行共享。并行扫描时，为每个 worker 建独立 prefs/config/tmp，避免锁文件、缓存污染和许可证/临时目录冲突。

## 2. Global Modeling Workflow

### Phase A: Literature And Target Decomposition

建模前先回答：

- 目标器件是什么：straight/rib/strip waveguide、bend、taper、DC、MMI、Y-branch、ring resonator、Bragg grating、grating coupler、MZI、aMZI、LT-aMZI、splitter、modulator、sensor 还是 inverse-design region？
- 论文给出的可验证指标是什么：`n_eff`、`n_g`、coupling ratio、FSR、T21、S11、FWHM、IL、ER、field map、mode profile？
- 论文仿真工具是什么：mode solver、FDTD、Interconnect、FEM、EIM 还是实验实测？
- 本次模型是完整 3D，还是 2D top-view effective-index approximation？
- 哪些结果必须复现，哪些只是背景或未来工程验证？

必须把复现边界写清楚。二维 EIM 结果不能表述为完整三维工艺签核结果。

### Phase B: Minimal Validation First

按从简单到复杂的顺序做：

1. 单根直波导，验证材料、端口、传播方向和低反射。
2. 单独基础单元，例如 bend、taper、DC、MMI、Y-branch、ring、Bragg section 或 grating unit。
3. 小型组合单元，例如 splitter+combiner、ring bus coupling、短 Bragg reflector、常规 MZI 或 aMZI。
4. 最终复杂器件，例如 LT-aMZI、Vernier、filter bank、sensor、modulator 或优化 splitter。

不要直接从完整器件开始调试；复杂器件失败时很难区分几何、端口、材料、网格、边界还是后处理问题。

### Phase C: Final Device Assembly

完整器件必须满足：

- 拓扑与论文一致。
- 材料分区明确。
- 端口边界垂直于局部直波导。
- 波导与非端口外边界有足够背景余量。
- 弯曲和过渡区无尖角。
- 参数和中心线长度可追溯。

### Phase D: Sweep And Evaluation

推荐顺序：

1. `lambda0 = 1.55[um]` 单点场图。
2. 小窗口粗扫，确认是否有峰谷。
3. 围绕峰谷做局部密扫。
4. 提取 FSR、峰值、谷值、S11、T21 和能量收支。
5. 再决定是否需要更细网格、更大背景、PML 或 3D 抽样验证。

## 3. 2D Effective-Index Photonic Model Rules

2D top-view 模型适合快速验证平面拓扑、耦合、相位差、FSR 和参数趋势。它不画真实垂直厚度，真实截面由有效折射率近似表示。

常用全局参数：

```text
lambda0 = 1.55[um]
freq0 = c_const/lambda0
w = 0.5[um]
n_bg = 1.444
n_wg_eff = <mode-solver-or-paper-value>
epsr_bg = n_bg^2
epsr_wg = n_wg_eff^2
mu_r = 1
sigma = 0
```

SOI strip 波导若来自 `500 nm x 220 nm` 结构，推荐先做截面 mode analysis 提取：

- `n_eff(lambda)`
- `n_g(lambda)`
- 模场是否单模
- 波长色散

若没有 mode solver，可先用论文或已有数据中的 `n_eff` / `n_g` 做 EIM，但报告中必须声明这是近似。

材料分区必须至少有：

- 背景/包层材料：例如 `mat_bg`, `epsr_bg`。
- 波导有效芯层材料：例如 `mat_wg`, `epsr_wg`。

常见材料错误：

- 忘记给波导域单独设置材料。
- 波导和背景域同属一个材料。
- 后续布尔操作后 material selection 丢失。

材料审计：

- `mat_bg` 覆盖所有非波导背景。
- `mat_wg` 覆盖所有波导路径。
- `mu_r = 1`。
- `sigma = 0`。

## 4. Geometry Rules

推荐用中心线参数化，再扩宽成波导域：

- 中心线用于计算长度、路径差和弯曲半径。
- 波导宽度由 `w` 控制。
- 不要用 x 坐标差代替实际中心线长度。

对于 aMZI/LT-aMZI：

- `DeltaL = L2 - L1` 必须沿中心线计算。
- 上臂和下臂应独立存在，不应退化为单根蛇形波导。

弯曲与过渡：

- 避免硬折角和 90 度尖角。
- 优先使用圆弧弯曲、S-bend、chamfer/fillet。
- port 前保留足够长的 straight section。
- SOI 500 nm 级 2D EIM 初值可用 `R_bend >= 5[um]`。
- 更稳健工程扫描可用 `R_bend = 5, 7.5, 10[um]`。

弯角不稳定时，不要先怪端口；先检查：

- 弯曲半径是否过小。
- 网格是否在弯曲区足够细。
- 波导是否离外边界太近。

Directional coupler geometry 必须明确：

- waveguide width `w`
- edge-to-edge gap `gap_dc`
- center-to-center spacing `w + gap_dc`
- coupling length `Lc`
- fan-in/fan-out 过渡形状
- four port directions

重要经验：独立 smooth coupler 的 `Lc` 不一定适用于最终主模型的 rounded-polyline coupler。最终器件使用哪种 fan-in/fan-out 几何，就应按同样几何重新标定 DC。

## 5. Numeric Port And Boundary Mode Analysis

对于 Wave Optics / Electromagnetic Waves, Frequency Domain：

1. 端口边界必须在计算域外边界上。
2. 端口边界必须垂直于局部直波导方向。
3. 端口前至少保留 `5-10 um` 直波导。
4. 每个 numeric port 建一个 `BoundaryModeAnalysis` study step。
5. 每个 port 的 `StudyStep` 绑定到对应 BMA。
6. 最后再做 `Frequency` 或 `Wavelength` sweep。

端口变量异常时，先排查：

- port selection 是否选到正确边界。
- scattering boundary 是否错误包含了 port 边界。
- port mode study 是否运行成功。
- Frequency study 是否引用了正确 port mode。
- 后处理 dataset 是否对应最终解。

外边界可以先用 scattering boundary 起步，但工程模型应比较：

- 更大背景尺寸。
- PML。
- scattering boundary 与 PML 对 T21/S11/field 的影响。

关键规则：scattering boundary selection 不得包含端口边界。

如果出现 `Undefined post expression`、S 参数全零、端口模塌缩、T21 扫谱全平，优先检查端口边界是否被 scattering boundary 覆盖。

## 6. General Device-Family Workflows

先按器件族选择验证目标，不要把所有片上光子问题都套成 MZI 问题。不同器件的核心物理证据不同：

| Device family | First validation | Key metrics |
|---|---|---|
| straight waveguide | two-port propagation | `S21`, `S11`, mode confinement, phase |
| bend | straight-vs-bend comparison | bend loss, radiation, reflection |
| taper / transition | width-change transmission | insertion loss, reflection, mode conversion |
| Y-branch / splitter | single-input multi-output split | split ratio, excess loss, imbalance |
| directional coupler | standalone 2x2 coupler | through/cross power, split error, coupling length |
| MMI coupler | standalone multimode section | split ratio, excess loss, wavelength tolerance |
| ring resonator | bus-ring or add-drop cell | resonance wavelength, FSR, Q, extinction |
| Bragg grating | periodic section | stopband, reflection, bandwidth |
| grating coupler | port/free-space or mode-coupled cell | coupling efficiency, bandwidth, angle/polarization sensitivity |
| MZI/aMZI/LT-aMZI | calibrated splitters plus arms | fringe FSR, extinction ratio, insertion loss |
| sensor/modulator | baseline plus perturbation | sensitivity, phase shift, resonance shift, loss |
| inverse-design region | fixed ports and fixed waveguides | objective, constraints, robustness, manufacturability proxy |

通用验证顺序：

1. 先做 straight waveguide 和 port smoke test。
2. 再做该器件族的最小可验证单元。
3. 再加入真实 routing、bends、transitions 和 boundary margin。
4. 最后做 wavelength/parameter sweep 和报告。

### Straight Waveguide, Bend, And Taper

直波导用于验证材料、端口、模式、边界和网格，是所有器件的最低层 smoke test。

弯曲器件重点看：

- bend radius 是否足够大。
- 弯曲区 mesh 是否足够细。
- 外边界/PML 是否足够远。
- 相同长度 straight reference 下的 bend excess loss。

taper 或 width transition 重点看：

- 输入/输出模式是否匹配。
- taper 是否足够 adiabatic。
- 是否出现高阶模式或反射。
- `S21`、`S11` 和 mode overlap。

### Splitter, Directional Coupler, MMI, And Y-Branch

splitter 类器件优先建立 standalone 多端口模型，先验证分束比和 excess loss，再接入上层系统。

通用指标：

```text
T_i1 = abs(Si1)^2
split_ratio_i = T_i1 / sum(T_outputs)
excess_loss = 1 - sum(T_outputs) - reflected_or_radiated_power
imbalance = max(split_ratio_i) - min(split_ratio_i)
```

directional coupler 和 MMI 的最优参数可能随 fan-in/fan-out、bend、gap mesh 和工作波长变化。最终系统使用哪种几何，standalone calibration 就应尽量复用同样几何。

### Resonant, Periodic, And Grating Devices

ring resonator、Bragg grating、grating coupler 和 photonic crystal 类器件不能只看单波长场图。

ring resonator 常看：

- resonance wavelength
- FSR
- loaded/intrinsic Q
- extinction ratio
- through/drop port spectra
- bus-ring coupling gap sensitivity

Bragg 或 periodic device 常看：

- stopband center
- stopband width
- reflection/transmission spectra
- number of periods convergence
- apodization/chirp influence

grating coupler 常看：

- coupling efficiency
- bandwidth
- polarization sensitivity
- angle sensitivity
- substrate/cladding/PML influence

### Sensor And Modulator

sensor/modulator 需要明确 perturbation 或 drive mechanism：

- 折射率变化。
- 几何变化。
- 温度变化。
- 电光/载流子/热光调制。
- 覆层或 analyte 变化。

先建立 passive baseline，再加入扰动。报告中区分 optical-only model、multiphysics-coupled model 和实验待验证假设。

## 7. MZI And LT-aMZI Workflows

常规 MZI 基本拓扑：

```text
Input splitter -> upper/lower arms -> output combiner -> output ports
```

常规 MZI 验收：

- 两个臂材料和宽度一致。
- `DeltaL` 沿中心线计算。
- 波长扫谱出现周期性干涉。
- FSR 与 `lambda^2/(n_g*DeltaL)` 同量级。

LT-aMZI 必须满足：

```text
DC1 -> unequal arms L1/L2 -> DC2 -> one loop reflector -> reflected return -> output at DC1
```

LT-aMZI 拓扑验收清单：

- DC1 是 2x2 directional coupler。
- DC2 是 2x2 directional coupler。
- DC1_E_top 连接上臂 L1。
- DC1_E_bottom 连接下臂 L2。
- DC2_E_top 与 DC2_E_bottom 由一个连续 loop reflector 连接。
- 最终模型没有右侧输出端口。
- 输入端口和输出端口都在左侧 DC1 附近。
- 光场显示从左上端口进入、分束、双臂传播、进入 loop、回程、从左下端口输出。

LT-aMZI FSR:

```text
FSR_LT = lambda^2 / (2 * n_g * DeltaL)
```

同一 `DeltaL` 下，LT-aMZI 的 FSR 约为常规 aMZI 的一半，因为 loop reflector 使相位差有效经历往返。

LT-aMZI 常见失败模式：

- 结构画成单根蛇形波导，而不是 DC1-双臂-DC2-loop。
- DC2 右侧仍放输出端口，导致模型变成普通 aMZI。
- loop 只连到一根波导，未连接 DC2 两个右侧端口。
- 输出测在右侧而不是 DC1 左侧下端口。
- `DeltaL` 用坐标差估算，导致 FSR 错。
- 弯角过尖，场泄漏到背景。
- 材料 selection 丢失，波导没有高折射率。
- DC 按单程 3 dB 标定后，往返 LT-aMZI 的峰值 T21 仍低；这时应优化 `gap_dc` / `Lc`，而不是重新怀疑 FSR。

## 8. Splitter And Coupler Calibration And Optimization

先建立 standalone 2x2 DC：

- Port1 输入。
- Port2/3/4 视几何定义为输出/through/cross。
- 扫 `gap_dc` 和 `Lc`。
- 在目标波长附近找到接近 50:50 的分束。

典型指标：

```text
abs(comp1.emw.S31)^2
abs(comp1.emw.S41)^2
throughput_right = abs(S31)^2 + abs(S41)^2
split_error = abs(abs(S31)^2 - abs(S41)^2)
```

选择标准：

- `split_error` 小。
- 总透过高。
- 反射低。
- 与最终主模型几何一致。

对于 MMI/Y-branch/splitter，目标不一定是 50:50，也可能是 1xN 均分、非均匀功分、低反射或宽带平坦响应。先定义目标分束向量，再评价误差。

通用 N 端口 splitter 指标：

```text
T_out_sum = sum(abs(Si1)^2 for output ports i)
R_in = abs(S11)^2
split_error = norm(normalized_outputs - target_split_vector)
uncollected = 1 - T_out_sum - R_in
```

LT-aMZI 是往返结构，单独 DC 的 3 dB 最优不一定是 Port2 峰值透过最优。

若 FSR 正确但峰值 T21 低：

1. 先确认不是波长采样漏峰。
2. 看峰值处 `S11` 是否高。
3. 看 `S11 + T21` 是否明显小于 1。
4. 扫 `Lc`。
5. 扫 `gap_dc`。
6. 做 `gap_dc x Lc` 联合扫描。

目标函数不要只看最高 `T21`，还要惩罚：

- 峰值不均匀。
- 强弱峰交替。
- 高反射 `S11`。
- 能量缺口。

示例目标：

```text
score = max(T21) - penalty(peak_nonuniformity) - penalty(S11_at_peak) - penalty(radiation_loss)
```

## 9. Mesh Strategy

先用预定义网格成功求解，再局部细化。不要一开始手写过细全局网格导致无法求解。

推荐策略：

- 波导芯层：至少 8-10 个单元跨宽度。
- DC gap：至少 5 个单元跨 gap。
- 弯曲区：与芯层同级或更细。
- 远离波导背景：尽量粗网格。
- 端口附近：保证模式边界和直波导足够分辨。

二维 EIM 初始参考：

- waveguide max element: `0.05-0.08 um`
- DC gap max element: `0.02-0.04 um`
- bend region max element: `0.05-0.08 um`
- far background: `0.2-0.4 um`

如果预定义网格更稳，应优先用预定义网格跑通，再添加局部 size features。

## 10. Postprocessing And Dataset Rules

在组件模型中，后处理表达式优先加组件前缀：

```text
comp1.emw.normE^2
abs(comp1.emw.S21)^2
10*log10(abs(comp1.emw.S21)^2)
abs(comp1.emw.S11)^2
```

如果物理接口 tag 是 `ewfd`，则使用：

```text
comp1.ewfd.normE^2
abs(comp1.ewfd.S21)^2
```

不要在不同模型里混用 `emw` 和 `ewfd`，先确认实际 physics tag。

绘图和 global evaluation 必须选择正确数据源：

- 单点场图：最终 Frequency Domain solution。
- 扫谱曲线：parametric / wavelength sweep solution。
- numeric port mode：不要误选 Boundary Mode Analysis dataset 来评估最终 S 参数。

经验规则：

- 若用户说“图画不出来”，先检查表达式是否缺少 `comp1.`。
- 若表达式不报错但结果不对，检查 dataset 是否选成最终解或正确 sweep dataset。
- 一次只验证一个表达式，避免多个失败叠加。

## 11. Energy-Budget Diagnostics

低输出时不要只看某一个 `Tij`。先按器件端口数建立能量收支。

两端口或反射输出器件可看：

```text
T21 = abs(S21)^2
R11 = abs(S11)^2
Ssum = T21 + R11
radiation_or_uncollected = 1 - Ssum
```

多输出 splitter/filter 可看：

```text
T_outputs = sum(abs(Si1)^2 for all intended output ports i)
R11 = abs(S11)^2
uncollected = 1 - T_outputs - R11
```

解释原则：

- FSR 正确但峰值低：通常说明干涉已形成，但耦合、端口匹配、边界或弯曲损耗仍需优化。
- `S11` 高：优先查端口匹配、回程耦合和 DC 参数。
- `Ssum` 远小于 1：优先查 scattering/PML、背景余量、弯曲辐射和网格。
- 单个波长的 `T21` 不能代表器件成败；干涉器、ring、Bragg、filter、grating coupler 通常必须扫波长或关键参数。

## 12. Boundary Between 2D And 3D Work

二维 EIM 适合：

- 拓扑正确性。
- FSR。
- 相位差趋势。
- 快速参数扫描。
- 设计候选筛选。

三维模型必须用于：

- 真实 SOI 截面模式。
- 垂直场分布。
- 弯曲/侧壁/包层真实损耗。
- 工艺厚度和刻蚀深度影响。
- grating coupler 或真实端面耦合。

推荐三维推进顺序：

1. 直 SOI strip 3D 端口模型。
2. 3D 截面 mode analysis 提取 `n_eff(lambda)` / `n_g(lambda)`。
3. 小型 3D DC 或 bend 单元验证。
4. 紧凑 3D 子结构抽样。
5. 再考虑完整 3D 复杂器件。

不要把未收敛或粗网格 3D 结果当作最终物理结论。若三维成本过高，应在报告中说明“3D 用于对应性检查，主结果限定在 2D EIM”。

## 13. External Optimization Workflow

适用于 inverse design、gap/Lc 扫描、结构参数搜索。

推荐结构：

1. Python/PowerShell 管理参数候选。
2. 每个候选生成 Java 源码或修改参数。
3. batch 顺序运行。
4. 输出 CSV/TXT 指标。
5. Python 聚合结果、绘图、排序。
6. 保留每个候选的模型、日志、关键图和 summary，前提是这些文件可被授权保存或分享。

对于昂贵仿真：

- 先粗扫，再局部密扫。
- 先少量代表点，再完整窗口。
- 保存 latest run 或 summary，便于中断续跑。
- 不要因为单个 foreground 超时就判定失败；检查输出目录和 log。

旧版 splitter / Hadamard 类外部逆向设计经验也适用，尤其当器件不是低维参数扫描，而是具有可设计区域或像素化材料分布时。

推荐外部优化结构：

1. 为每个输入条件建立一个 forward model，例如两个单输入模型。
2. 只参数化真正允许设计的区域，例如中心 square design region。
3. 固定波导臂、输入/输出端口和背景，不要让优化变量误改固定光路。
4. Python 负责候选向量生成、Java 源码补丁、batch 运行、指标解析和优化器更新。
5. 先用简单稳健优化器；昂贵且有噪声的目标可用 SPSA 或小规模 NSGA。

Design-region discipline:

- design region 使用独立 selection。
- fixed waveguide arms 使用独立 selection。
- fixed-core material 只覆盖固定波导臂。
- design-region material 只覆盖设计区。
- 背景材料不应覆盖设计区或固定波导芯层。
- 不要让固定芯层材料意外覆盖整个中心设计区。

这条规则也适用于非像素化器件：MZI 的 arms、DC、loop、background 应有清楚 selection 和材料归属，避免一次布尔操作后材料选择失效。

Resolution refinement:

- 保留上一阶段 best vector。
- 按分辨率保存备份和 manifest。
- 尝试 nearest-neighbor lifting 和 bilinear lifting。
- 先评估两种 lifting，再继续优化。
- 不要默认更平滑的插值一定更好。

多输入器件中，不能把多个单输入激励的输出功率简单解释为单次能量守恒。

例如 splitter 类问题：

- `trans_total = sumA + sumB` 可表示两个单输入模型的总指标。
- 若 `trans_total > 1`，不一定违反单输入能量守恒，因为它聚合了多个独立激励。
- 更有物理意义的是分别看每个输入条件下的分束比，例如 `T_aa:T_ab` 与 `T_ba:T_bb`。

对单输入扫谱器件，如 MZI/LT-aMZI/ring/Bragg/filter，更应关注：

- `abs(S21)^2`
- `abs(S11)^2`
- `S11 + T21`
- 峰值/谷值位置
- FSR、resonance spacing、stopband 或峰值均匀性

从优化向工程设计推进时，先导出可视化预览，而不要直接宣称可制造：

- density preview
- binary preview
- SVG/PNG layout preview
- CSV mask
- layout manifest

阈值化或二值化预览只是理解结构的中间产物，不等同于最终 GDS、PDK 合规版图或三维工艺可制造结果。若阈值化已经降低性能，应在报告中明确说明。

## 14. Reporting And Deliverables

每个完整项目建议交付：

- model file(s)，前提是可授权分享。
- build scripts，例如 `Build*.java`。
- run scripts 或 sweep scripts。
- batch logs。
- CSV/TXT result tables。
- field plots。
- spectrum plots。
- model-quality audit report。
- modeling-step report。
- optimization-analysis report。
- final slides or presentation document。

报告中必须区分：

- 已由全波仿真验证。
- 仅由 reduced / analytical 模型验证。
- 仅为候选优化。
- 仍需三维或实验验证。

避免过度表述：

- 不要把二维 EIM 说成真实 3D 工程定型。
- 不要把局部扫描最优说成全局最优。
- 不要把漂亮场图当作唯一证据。
- 不要忽略 `S11`、能量收支和边界损耗。

## 15. LT-aMZI Project Experience

LT-aMZI 复现中的关键经验：

- 用户若强调论文 Fig. 1(a) 拓扑，必须避免单蛇形波导，必须建 DC1、双臂、DC2 和 loop reflector。
- `Design1-4` 的验收主指标可为 FSR: `6.4 / 3.2 / 1.6 / 0.8 nm`。
- `DeltaL` 必须沿中心线计算。
- 材料分区必须显式：`mat_bg` 和 `mat_wg`。
- 弯角必须平滑，不能依赖尖角传播。
- 绘图表达式应使用 `comp1.` 前缀，数据源选最终解。
- DC 标定得到单程 3 dB 后，仍可能在往返 LT-aMZI 中出现低 T21。
- 对较长 path-difference 设计，减小 `gap_dc` 可能比单独改 `Lc` 更显著提高峰值透过，但可能牺牲 comb 均匀性。
- 最终应同时保留“论文保真模型”和“高透过优化候选模型”，并在报告中清楚区分。

## 16. Quick Debug Table

| Symptom | Check First | Common Fix |
|---|---|---|
| No S parameter or undefined expression | physics tag, dataset, port mode study | Use `comp1.`, select final solution, bind BMA |
| T21 all zero | port selection, scattering boundary covering port | Exclude ports from scattering boundary |
| Field leaks into background | bends, mesh, material selection | Increase `R_bend`, refine bend mesh, check `mat_wg` |
| Field exists but no fringes | DC splitting, `DeltaL`, sweep range | Calibrate DC, recompute centerline `DeltaL` |
| FSR wrong | `n_g`, `DeltaL`, LT round-trip formula | Use `lambda^2/(2*n_g*DeltaL)` for LT-aMZI |
| Splitter imbalance | target split, geometry symmetry, mesh | sweep splitter length/gap/width and inspect output phases |
| Ring resonance missing | coupling gap, ring radius, sweep resolution | widen sweep, refine wavelength step, check bus-ring coupling |
| Bragg stopband wrong | period, effective index, number of periods | verify Bragg condition and sweep enough periods |
| Peak low but FSR correct | S11, round-trip coupling, port matching | Sweep `gap_dc/Lc`, compare PML/boundaries |
| 3D solve difficult | mesh, port window, model size | Start from straight waveguide/substructure and predefined mesh |

## 17. Default Actions

当用户要求“复现某篇论文器件”：

1. 先读论文或用户表单，提取拓扑、尺寸、材料、端口、目标指标。
2. 判断器件族：waveguide、bend、taper、splitter、coupler、resonator、grating、interferometer、sensor、modulator 或 inverse-design region。
3. 建立最小验证模型，不直接冲完整器件。
4. 写可重复 Java/batch 脚本。
5. 单独校准关键模块。
6. 装配完整器件。
7. 做单点场图和扫谱/参数扫描。
8. 用理论公式和论文数据对比。
9. 输出模型、数据、图像、报告和下一步建议。

当用户要求“优化仿真结果”：

1. 先确认是否已经复现核心物理指标。
2. 再诊断低性能来自端口、边界、耦合、弯曲、网格还是材料。
3. 按器件族选择指标：splitter 看 imbalance/excess loss，ring 看 Q/ER/FSR，grating 看 coupling/bandwidth，interferometer 看 FSR/ER/IL。
4. 明确目标函数和副作用。
5. 设计小规模参数扫描。
6. 报告候选，不夸大全局最优。

当用户要求“上传、发布、共享 skill 或模型”：

1. 扫描本机路径、用户名、license/token、专有文档、私有数据。
2. 确保项目名、skill 名和仓库名不包含第三方商标。
3. 保留兼容性说明、非隶属声明和商标归属。
4. 不上传 `.mph`、log 或论文 PDF，除非明确可公开。
5. 使用真实用户作者信息提交，不使用临时 agent author。
