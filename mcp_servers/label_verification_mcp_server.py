"""MCP server: product label sticker verification (Phase 1)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from label_verification_lib import verify_labels

mcp = FastMCP("label-verification")


@mcp.tool()
def label_verification(
    standard_image_url: str,
    actual_image_url: str,
    verification_prompt: str = "",
) -> str:
    """对比验证标准贴纸与实际贴纸，返回 JSON 核对报告。

    下载两张图片，调用视觉模型逐项比对，返回包含 overall_result、checks、
    differences_summary 的 JSON 字符串（无 Markdown 包裹）。

    Args:
        standard_image_url: 标准标签贴纸图片 URL（HTTP/HTTPS）
        actual_image_url: 实际标签贴纸图片 URL（HTTP/HTTPS）
        verification_prompt: 可选核对重点；为空时使用默认全量核对清单
    """
    try:
        report = verify_labels(
            standard_image_url=standard_image_url.strip(),
            actual_image_url=actual_image_url.strip(),
            verification_prompt=verification_prompt,
        )
        return json.dumps(report, ensure_ascii=False)
    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "error_type": type(e).__name__,
                "hint": "检查 URL、LABEL_VISION_API_BASE/KEY/MODEL 环境变量及视觉模型可用性",
            },
            ensure_ascii=False,
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")
