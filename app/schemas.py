"""Pydantic 请求/响应模型。"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

PositiveInt = Annotated[int, Field(ge=1)]


class BatchIn(BaseModel):
    roll_no: str = Field(..., min_length=1, description="胶卷编号")
    expected_start: int = Field(..., ge=0, description="预期帧号起始（含）")
    expected_end: int = Field(..., ge=0, description="预期帧号结束（含）")
    frames: list[int] = Field(..., min_length=1, description="本批扫描帧号列表")
    batch_id: str | None = Field(
        None, description="客户端批次号（可选）；留空则按内容生成"
    )

    @field_validator("roll_no", "batch_id")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("expected_end")
    @classmethod
    def _check_range(cls, v: int, info) -> int:
        start = info.data.get("expected_start")
        if start is not None and v < start:
            raise ValueError("expected_end 不能小于 expected_start")
        return v


class BatchResult(BaseModel):
    batch_id: str
    roll_no: str
    repeated: bool = Field(..., description="True=内容相同的批次已导入过，本次未做任何更改")
    added_frames: list[int]
    duplicates: list[int] = Field(..., description="重复帧（批内重复 + 胶卷已有），只计一次")
    merged_frames: list[int] = Field(..., description="导入后该胶卷的全部帧号（去重排序）")
    expected_ranges: list[list[int]]
    missing_ranges: list[list[int]] = Field(..., description="预期范围内的连续缺帧区间")
    out_of_range_frames: list[int] = Field(..., description="落在全部预期范围之外的帧")
    created_at: str | None = None


class BatchPrecheckOut(BaseModel):
    """预检单：相对创建时胶卷状态的预演结果（此时尚未写入任何批次）。"""

    precheck_id: str = Field(..., description="预检单 ID，凭此确认导入")
    roll_no: str
    batch_id: str | None = Field(
        ..., description="预检提交时携带的客户端批次号；留空时确认后服务端自动生成"
    )
    expected_start: int = Field(..., description="本批预期帧号起始（含）")
    expected_end: int = Field(..., description="本批预期帧号结束（含）")
    raw_frames: list[int] = Field(
        ..., description="提交的原始帧列表（含批内重复，保留提交时的原始顺序）"
    )
    added_frames: list[int] = Field(
        ..., description="若此刻导入将新增的帧号（去重排序）"
    )
    duplicates: list[int] = Field(
        ..., description="重复帧（批内重复 + 胶卷已有），只计一次"
    )
    current_expected_ranges: list[list[int]] = Field(
        ..., description="创建预检单时胶卷已有的合并预期覆盖闭区间"
    )
    post_import_expected_ranges: list[list[int]] = Field(
        ..., description="导入后胶卷的合并预期覆盖闭区间"
    )
    post_import_missing_ranges: list[list[int]] = Field(
        ..., description="导入后预期范围内的连续缺帧区间"
    )
    state_fingerprint: str = Field(
        ...,
        description="创建时胶卷状态（预期范围 + 实扫帧集合）的 SHA-256 指纹，确认时复核",
    )
    confirmed: bool = Field(..., description="是否已确认导入")
    created_at: str
    confirmed_at: str | None = None


class BatchPrecheckConfirmOut(BatchResult):
    """确认预检单的结果：与 POST /batches 响应同构，另带预检单信息。

    同一预检单再次确认原样返回首次结果（import_status_code 也与首次一致）。
    """

    precheck_id: str
    confirmed: bool = Field(
        ..., description="True=本次为重复确认，返回的是首次导入冻结的结果"
    )
    import_status_code: int = Field(
        ..., description="首次导入对应的状态码：201 新建 / 200 内容重复"
    )


class QualityAlertThresholds(BaseModel):
    duplicate_rate: float = Field(
        ..., description="批内重复率告警阈值（达到即触发 HIGH_DUPLICATE_RATE）"
    )
    gap_length: int = Field(
        ..., description="预期内最长缺口告警阈值（帧数，达到即触发 LONG_MISSING_GAP）"
    )


class BatchQualityOut(BaseModel):
    batch_id: str
    roll_no: str
    expected_start: int = Field(..., description="本批预期帧号起始（含）")
    expected_end: int = Field(..., description="本批预期帧号结束（含）")
    frame_count: int = Field(..., description="原始帧列表长度（含批内重复）")
    unique_frame_count: int = Field(..., description="去重后的帧数")
    duplicate_rate: float = Field(
        ...,
        description="批内重复率 = (frame_count − unique_frame_count) / frame_count，保留 4 位小数",
    )
    out_of_range_frames: list[int] = Field(
        ..., description="落在本批预期闭区间之外的帧（去重排序）"
    )
    longest_scanned_run: list[int] | None = Field(
        ...,
        description="按原始顺序压缩出的最长连续扫到段 [start, end]（闭区间，并列取先出现者）",
    )
    longest_scanned_run_length: int = Field(..., description="最长连续扫到段长度（帧数）")
    longest_gap: list[int] | None = Field(
        ..., description="预期闭区间内的最长缺帧段 [start, end]（并列取帧号最小者）；无缺口为 null"
    )
    longest_gap_length: int = Field(..., description="预期闭区间内最长缺口长度（帧数）")
    segment_count: int = Field(
        ..., description="原始帧列表按原始顺序压缩成连续段后的段数"
    )
    alerts: list[str] = Field(
        ...,
        description="稳定告警代码，按阈值触发：HIGH_DUPLICATE_RATE（批内重复率）、"
        "FRAMES_OUT_OF_RANGE（越界帧）、LONG_MISSING_GAP（预期内缺口长度）",
    )
    alert_thresholds: QualityAlertThresholds = Field(
        ..., description="本次评估使用的告警阈值"
    )
    created_at: str = Field(..., description="批次导入时间（UTC ISO-8601）")


class RollState(BaseModel):
    roll_no: str
    expected_ranges: list[list[int]]
    frames: list[int]
    missing_ranges: list[list[int]]
    out_of_range_frames: list[int]
    total_frames: int
    batch_count: int
    batches: list["BatchMeta"]


class BatchMeta(BaseModel):
    batch_id: str
    expected_start: int
    expected_end: int
    frames: list[int]
    added_frames: list[int]
    duplicates: list[int]
    created_at: str


class RollSummary(BaseModel):
    roll_no: str
    total_frames: int
    batch_count: int
    missing_ranges: list[list[int]]


class FrameBatchRef(BaseModel):
    batch_id: str = Field(
        ..., description="扫到该帧的有效批次；列表按批次原导入顺序排列"
    )
    occurrence_count: int | None = Field(
        ...,
        description="该帧在该批**原始帧列表**中的出现次数；"
        "旧批次没有原始列表时为 null（无法区分重复次数，不做推断）",
    )


class FrameProvenanceItem(BaseModel):
    frame_no: int
    first_scan_batch_id: str = Field(
        ...,
        description="最早有效批次（当前帧归属批次）；撤销批次后按剩余批次实时重算，首扫归属随之转移",
    )
    in_expected_coverage: bool = Field(
        ..., description="该帧是否位于胶卷当前预期覆盖（合并后的预期闭区间）内"
    )
    batches: list[FrameBatchRef] = Field(
        ..., description="扫描过该帧的全部有效批次，按批次原导入顺序排列"
    )


class FrameProvenanceOut(BaseModel):
    roll_no: str
    frames: list[FrameProvenanceItem] = Field(
        ..., description="本页帧的溯源信息，按帧号升序（只含实际存在的帧号）"
    )
    next_cursor: int | None = Field(
        ...,
        description="下一页游标（本页末帧号），传入 cursor 续读；无后续帧时为 null",
    )


class HealthOut(BaseModel):
    status: str
    db: str


# ---------- 扫描瑕疵复核 ----------

# 瑕疵类型（对外契约，稳定取值，勿随意改动）
DefectType = Literal["模糊", "划痕", "曝光异常"]


class DefectMarkIn(BaseModel):
    position: int = Field(
        ..., ge=0, description="批次原始帧列表中的位置（0 起算，非负整数）"
    )
    defect_type: DefectType = Field(
        ..., description="瑕疵类型：模糊 / 划痕 / 曝光异常"
    )


class BatchDefectsIn(BaseModel):
    defects: list[DefectMarkIn] = Field(
        ...,
        description="整批瑕疵标记，整体替换该批现有标记；空列表表示清除该批全部标记",
    )


class DefectMarkOut(BaseModel):
    position: int = Field(..., description="批次原始帧列表中的位置（0 起算）")
    frame_no: int = Field(..., description="该位置上的帧号")
    defect_type: DefectType = Field(..., description="瑕疵类型：模糊 / 划痕 / 曝光异常")


class BatchDefectsOut(BaseModel):
    batch_id: str
    roll_no: str
    defects: list[DefectMarkOut] = Field(
        ..., description="本次替换后生效的全部瑕疵标记（按位置升序）"
    )
    updated_at: str = Field(..., description="本次替换时间（UTC ISO-8601）")


class DefectQueueItem(BaseModel):
    frame_no: int = Field(
        ..., description="全部有效扫描出现均被标记瑕疵的帧号"
    )
    defect_occurrences: int = Field(
        ..., description="该帧被标记瑕疵的扫描出现次数（入队时等于其有效出现总次数）"
    )


class DefectQueueOut(BaseModel):
    roll_no: str
    items: list[DefectQueueItem] = Field(
        ..., description="待复核帧列表，按帧号升序；空列表表示当前无全瑕疵帧"
    )


class RescanClaimIn(BaseModel):
    claimant: str = Field(..., min_length=1, description="领取人标识")
    max_frames: PositiveInt = Field(..., description="本次最多领取的帧数（正整数）")
    ttl_seconds: PositiveInt = Field(..., description="认领有效秒数（正整数），到期后帧段自动让出")

    @field_validator("claimant")
    @classmethod
    def _strip_claimant(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("claimant 不能为空")
        return v


class RescanClaimOut(BaseModel):
    id: str
    roll_no: str
    claimant: str
    frame_start: int = Field(..., description="认领帧段起始（含）")
    frame_end: int = Field(..., description="认领帧段结束（含）")
    frame_count: int
    max_frames: int
    ttl_seconds: int
    created_at: str
    expires_at: str
    remaining_missing_ranges: list[list[int]] = Field(
        ..., description="该任务帧段中目前仍缺失（未扫到）的连续闭区间"
    )


class RescanReceiptIn(BaseModel):
    batch_id: str = Field(..., min_length=1, description="本次补扫批次号（必填）")
    frames: list[int] = Field(
        ..., min_length=1, description="本次实际扫到的非空帧号列表（原始列表，至少 1 个）"
    )

    @field_validator("batch_id")
    @classmethod
    def _strip_batch_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("batch_id 不能为空")
        return v


class RescanReceiptOut(BaseModel):
    id: str = Field(..., description="回执 ID")
    claim_id: str
    roll_no: str
    claimant: str
    frame_start: int = Field(..., description="认领帧段起始（含）")
    frame_end: int = Field(..., description="认领帧段结束（含）")
    batch_id: str = Field(..., description="本次补扫导入的批次号")
    frames: list[int] = Field(
        ..., description="提交的原始帧列表（含批内重复，保序）"
    )
    added_frames: list[int] = Field(..., description="本批新补齐的帧号（去重排序）")
    duplicates: list[int] = Field(
        ..., description="重复帧（批内重复 + 胶卷已有），只计一次"
    )
    repeated: bool = Field(
        ...,
        description="True=相同认领、批次号与原始帧列表的重试，回执为已存记录，未重复导入",
    )
    remaining_missing_ranges: list[list[int]] = Field(
        ..., description="结案后该认领帧段内仍缺失（未扫到）的连续闭区间"
    )
    created_at: str


class RollSnapshotOut(BaseModel):
    snapshot_id: str = Field(..., description="快照 ID，可长期用于差异查询")
    roll_no: str
    expected_ranges: list[list[int]] = Field(
        ..., description="固化时的预期覆盖闭区间（合并后）"
    )
    frames: list[int] = Field(..., description="固化时的实扫帧（去重排序）")
    missing_ranges: list[list[int]] = Field(
        ..., description="固化时的缺帧闭区间（预期范围内未扫到的连续段）"
    )
    created_at: str = Field(..., description="快照创建时间（UTC ISO-8601）")


class RangeDiff(BaseModel):
    added: list[list[int]] = Field(
        ..., description="当前相对快照**新增**的闭区间（当前有、快照无）"
    )
    removed: list[list[int]] = Field(
        ..., description="当前相对快照**消失**的闭区间（快照有、当前无）"
    )


class SnapshotDiffOut(BaseModel):
    snapshot_id: str
    roll_no: str
    roll_exists: bool = Field(
        ...,
        description="查询时胶卷是否存在（最后一批被撤销后为 false，此时当前状态按空处理）",
    )
    snapshot_created_at: str
    compared_at: str = Field(..., description="差异计算时间（UTC ISO-8601）")
    expected: RangeDiff = Field(..., description="预期覆盖的差异（区间集合运算）")
    frames: RangeDiff = Field(..., description="实扫帧的差异（帧集合先压成闭区间再比较）")
    missing: RangeDiff = Field(..., description="缺帧区间的差异（区间集合运算）")


RollState.model_rebuild()
