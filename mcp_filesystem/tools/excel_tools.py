"""Excel 工具 - excel_edit（单工具）.

整合前（42个工具）：
- read_excel, write_excel, update_excel_cells, list_sheets, get_excel_info,
  excel_to_csv, csv_to_excel, create_workbook, create_worksheet, copy_worksheet,
  delete_worksheet, rename_worksheet, get_workbook_metadata, format_range,
  apply_formula, validate_formula_syntax, read_excel_metadata, merge_cells,
  unmerge_cells, get_merged_cells, copy_range, delete_range, validate_excel_range,
  get_data_validation_info, insert_rows, insert_columns, delete_sheet_rows,
  delete_sheet_columns, create_chart, create_table, create_pivot_table, ...

整合后（1个工具）：
- excel_edit: 精确编辑 Excel 文件
  - cells: 更新单元格
  - formula: 应用公式
  - format: 格式化范围
  - range: 范围操作（copy/delete/merge/unmerge）
  - sheet_ops: 工作表操作（create/delete/rename/copy）
  - row_col_ops: 行列操作（insert_rows/insert_cols/delete_rows/delete_cols）
  - chart: 创建图表（bar/line/pie/scatter）

说明：
- Excel 文件的读取使用 fs_read
- Excel 文件的写入使用 fs_write
- Excel 元数据获取使用 fs_ops("info")
"""

from typing import Any, Dict, List, Literal, Optional, Union

from mcp.server.fastmcp.utilities.logging import get_logger

from ..security import PathValidator

logger = get_logger(__name__)


def _normalize_mcp_param(value: Any, expected_type: type = None) -> Any:
    """规范化 MCP client 传递的参数.
    
    MCP client 可能将单个值错误包装成列表，此函数用于解包。
    
    Args:
        value: 原始参数值
        expected_type: 期望的类型（用于类型检查）
        
    Returns:
        规范化后的值
        
    Examples:
        _normalize_mcp_param(['hello'], str) -> 'hello'  # 单元素列表解包为字符串
        _normalize_mcp_param([{'a': 1}], dict) -> {'a': 1}  # 单元素列表解包为字典
        _normalize_mcp_param([['a', 'b']], list) -> [['a', 'b']]  # 2D数组保持原样
        _normalize_mcp_param([['a'], ['b']], list) -> [['a'], ['b']]  # 2D数组保持原样
    """
    # 如果是列表且只有一个元素
    if isinstance(value, list) and len(value) == 1:
        single_item = value[0]
        
        # 如果期望类型是字符串，且单元素是字符串，则解包
        if expected_type == str and isinstance(single_item, str):
            return single_item
        
        # 如果期望类型是字典，且单元素是字典，则解包
        if expected_type == dict and isinstance(single_item, dict):
            return single_item
        
        # 如果期望类型是列表
        if expected_type == list:
            if isinstance(single_item, list):
                # 检查是否是 2D 数组（列表的列表）
                if single_item and isinstance(single_item[0], list):
                    # 这是 2D 数组，保持原样（不解包）
                    return value
                else:
                    # 这是普通列表（如字符串列表），解包
                    return single_item
        
        # 其他情况：如果单元素类型匹配期望类型，解包
        if expected_type and isinstance(single_item, expected_type):
            return single_item
    
    return value


async def excel_edit(
    path: str,
    edit_type: Literal["cells", "formula", "format", "range", "sheet_ops", "row_col_ops", "chart"],
    excel_ops: Any,
    validator: PathValidator,
    *,
    sheet: Optional[str] = None,
    # cells 模式
    updates: Optional[List[Dict[str, Any]]] = None,
    # formula 模式
    cell: Optional[str] = None,
    formula: Optional[str] = None,
    # format 模式
    range: Optional[str] = None,
    style: Optional[Dict[str, Any]] = None,
    # range 模式
    operation: Optional[Literal["copy", "delete", "merge", "unmerge"]] = None,
    source_range: Optional[str] = None,
    target_range: Optional[str] = None,
    # sheet_ops 模式
    sheet_operation: Optional[Literal["create", "delete", "rename", "copy"]] = None,
    target_sheet: Optional[str] = None,
    new_name: Optional[str] = None,
    # row_col_ops 模式
    row_col_operation: Optional[Literal["insert_rows", "insert_cols", "delete_rows", "delete_cols"]] = None,
    start_index: Optional[int] = None,
    count: int = 1,
    # chart 模式
    chart_type: Optional[Literal["bar", "line", "pie", "scatter"]] = None,
    data_range: Optional[str] = None,
    target_cell: Optional[str] = None,
    chart_title: Optional[str] = None,
) -> Dict[str, Any]:
    """精确编辑 Excel 文件的特定部分.
    
    整合了 30+ 个 Excel 编辑工具，通过 edit_type 参数区分：
    - cells: update_excel_cells
    - formula: apply_formula
    - format: format_range
    - range: copy_range, delete_range, merge_cells, unmerge_cells
    - sheet_ops: create_worksheet, delete_worksheet, rename_worksheet, copy_worksheet
    
    Args:
        path: 文件路径
        edit_type: 编辑类型
        excel_ops: Excel 操作实例
        validator: 路径验证器
        sheet: 工作表名称
        
        # cells 模式参数
        updates: 更新列表 [{"cell": "A1", "value": "new"}, ...]
        
        # formula 模式参数
        cell: 单元格地址
        formula: 公式（如 "=SUM(A1:A10)"）
        
        # format 模式参数
        range: 格式化范围
        style: 样式字典 {
            "bold": bool,
            "italic": bool,
            "font_size": int,
            "font_color": str,
            "bg_color": str,
            "border": str,
            "number_format": str,
            "alignment": str
        }
        
        # range 模式参数
        operation: 范围操作类型 (copy/delete/merge/unmerge)
        source_range: 源范围
        target_range: 目标范围
        
        # sheet_ops 模式参数
        sheet_operation: 工作表操作类型 (create/delete/rename/copy)
        target_sheet: 目标工作表名
        new_name: 新名称（用于 rename）
        
    Returns:
        操作结果字典
        
    Examples:
        # 更新单元格
        excel_edit("data.xlsx", "cells", updates=[
            {"cell": "A1", "value": "Hello"},
            {"cell": "B1", "value": 123}
        ])
        
        # 应用公式
        excel_edit("data.xlsx", "formula", cell="D1", formula="=SUM(A1:C1)")
        
        # 格式化
        excel_edit("data.xlsx", "format", range="A1:C10", style={
            "bold": True,
            "bg_color": "FFFF00",
            "border": "thin"
        })
        
        # 合并单元格
        excel_edit("data.xlsx", "range", operation="merge", range="A1:C1")
        
        # 创建工作表
        excel_edit("data.xlsx", "sheet_ops", sheet_operation="create", target_sheet="NewSheet")
    """
    abs_path, allowed = await validator.validate_path(path)
    if not allowed:
        raise ValueError(f"Path outside allowed directories: {path}")
    
    # 规范化参数（处理 MCP client 可能将值包装成列表的情况）
    if updates is not None:
        # updates 应该是字典列表，如果是单元素列表且元素是字典列表，解包
        updates = _normalize_mcp_param(updates, expected_type=list)
    
    if style is not None:
        # style 应该是字典，如果是单元素列表且元素是字典，解包
        style = _normalize_mcp_param(style, expected_type=dict)
    
    if edit_type == "cells":
        if not updates:
            raise ValueError("updates is required for cells edit_type")
        result = await excel_ops.update_excel_cells(
            path=path,
            updates=updates,
            sheet=sheet,
        )
        return {
            "success": True,
            "edit_type": "cells",
            "path": validator.real_to_virtual(abs_path),
            **result,
        }
    
    elif edit_type == "formula":
        if not cell or not formula:
            raise ValueError("cell and formula are required for formula edit_type")
        result = await excel_ops.apply_formula(
            path=path,
            sheet=sheet or "Sheet1",
            cell=cell,
            formula=formula,
        )
        return {
            "success": True,
            "edit_type": "formula",
            "path": validator.real_to_virtual(abs_path),
            "cell": cell,
            "formula": formula,
            **result,
        }
    
    elif edit_type == "format":
        if not range and not cell:
            raise ValueError("range or cell is required for format edit_type")
        if not style:
            raise ValueError("style is required for format edit_type")
        
        format_range = range or cell
        result = await excel_ops.format_range(
            path=path,
            sheet=sheet or "Sheet1",
            cell_range=format_range,
            bold=style.get("bold"),
            italic=style.get("italic"),
            font_size=style.get("font_size"),
            font_color=style.get("font_color"),
            bg_color=style.get("bg_color"),
            border=style.get("border"),
            number_format=style.get("number_format"),
            alignment=style.get("alignment"),
        )
        return {
            "success": True,
            "edit_type": "format",
            "path": validator.real_to_virtual(abs_path),
            "range": format_range,
            **result,
        }
    
    elif edit_type == "range":
        if not operation:
            raise ValueError("operation is required for range edit_type")
        
        if operation == "copy":
            if not source_range or not target_range:
                raise ValueError("source_range and target_range are required for copy operation")
            # Parse source_range (e.g., "A1:C10" -> start_cell="A1", end_cell="C10")
            if ":" in source_range:
                src_start, src_end = source_range.split(":")
            else:
                src_start = src_end = source_range
            # target_range is just start position
            tgt_start = target_range.split(":")[0] if ":" in target_range else target_range
            result = await excel_ops.copy_range(
                path=path,
                sheet=sheet or "Sheet1",
                source_start=src_start,
                source_end=src_end,
                target_start=tgt_start,
            )
        elif operation == "delete":
            delete_range = range or source_range
            if not delete_range:
                raise ValueError("range is required for delete operation")
            # Parse range (e.g., "A1:C10" -> start_cell="A1", end_cell="C10")
            if ":" in delete_range:
                start_cell, end_cell = delete_range.split(":")
            else:
                start_cell = end_cell = delete_range
            result = await excel_ops.delete_range(
                path=path,
                sheet=sheet or "Sheet1",
                start_cell=start_cell,
                end_cell=end_cell,
            )
        elif operation == "merge":
            merge_range = range or source_range
            if not merge_range:
                raise ValueError("range is required for merge operation")
            # Parse range (e.g., "A1:C1" -> start_cell="A1", end_cell="C1")
            if ":" in merge_range:
                start_cell, end_cell = merge_range.split(":")
            else:
                raise ValueError("merge operation requires a range with format 'A1:C1'")
            result = await excel_ops.merge_cells(
                path=path,
                sheet=sheet or "Sheet1",
                start_cell=start_cell,
                end_cell=end_cell,
            )
        elif operation == "unmerge":
            unmerge_range = range or source_range
            if not unmerge_range:
                raise ValueError("range is required for unmerge operation")
            # Parse range (e.g., "A1:C1" -> start_cell="A1", end_cell="C1")
            if ":" in unmerge_range:
                start_cell, end_cell = unmerge_range.split(":")
            else:
                raise ValueError("unmerge operation requires a range with format 'A1:C1'")
            result = await excel_ops.unmerge_cells(
                path=path,
                sheet=sheet or "Sheet1",
                start_cell=start_cell,
                end_cell=end_cell,
            )
        else:
            raise ValueError(f"Unknown range operation: {operation}")
        
        return {
            "success": True,
            "edit_type": "range",
            "operation": operation,
            "path": validator.real_to_virtual(abs_path),
            **result,
        }
    
    elif edit_type == "sheet_ops":
        if not sheet_operation:
            raise ValueError("sheet_operation is required for sheet_ops edit_type")
        
        if sheet_operation == "create":
            if not target_sheet:
                raise ValueError("target_sheet is required for create operation")
            result = await excel_ops.create_worksheet(
                path=path,
                sheet_name=target_sheet,
            )
        elif sheet_operation == "delete":
            delete_sheet = sheet or target_sheet
            if not delete_sheet:
                raise ValueError("sheet or target_sheet is required for delete operation")
            result = await excel_ops.delete_worksheet(
                path=path,
                sheet_name=delete_sheet,
            )
        elif sheet_operation == "rename":
            if not sheet or not new_name:
                raise ValueError("sheet and new_name are required for rename operation")
            result = await excel_ops.rename_worksheet(
                path=path,
                old_name=sheet,
                new_name=new_name,
            )
        elif sheet_operation == "copy":
            if not sheet or not target_sheet:
                raise ValueError("sheet and target_sheet are required for copy operation")
            result = await excel_ops.copy_worksheet(
                path=path,
                source_sheet=sheet,
                target_sheet=target_sheet,
            )
        else:
            raise ValueError(f"Unknown sheet operation: {sheet_operation}")
        
        return {
            "success": True,
            "edit_type": "sheet_ops",
            "sheet_operation": sheet_operation,
            "path": validator.real_to_virtual(abs_path),
            **result,
        }

    elif edit_type == "row_col_ops":
        if not row_col_operation:
            raise ValueError("row_col_operation is required for row_col_ops edit_type")
        if start_index is None:
            raise ValueError("start_index is required for row_col_ops edit_type")

        if row_col_operation == "insert_rows":
            result = await excel_ops.insert_rows(
                path=path,
                sheet=sheet or "Sheet1",
                start_row=start_index,
                count=count,
            )
        elif row_col_operation == "insert_cols":
            result = await excel_ops.insert_columns(
                path=path,
                sheet=sheet or "Sheet1",
                start_col=start_index,
                count=count,
            )
        elif row_col_operation == "delete_rows":
            result = await excel_ops.delete_rows(
                path=path,
                sheet=sheet or "Sheet1",
                start_row=start_index,
                count=count,
            )
        elif row_col_operation == "delete_cols":
            result = await excel_ops.delete_columns(
                path=path,
                sheet=sheet or "Sheet1",
                start_col=start_index,
                count=count,
            )
        else:
            raise ValueError(f"Unknown row_col_operation: {row_col_operation}")

        return {
            "success": True,
            "edit_type": "row_col_ops",
            "row_col_operation": row_col_operation,
            "path": validator.real_to_virtual(abs_path),
            **result,
        }

    elif edit_type == "chart":
        if not chart_type or not data_range or not target_cell:
            raise ValueError("chart_type, data_range, and target_cell are required for chart edit_type")

        result = await excel_ops.create_chart(
            path=path,
            sheet=sheet or "Sheet1",
            data_range=data_range,
            chart_type=chart_type,
            target_cell=target_cell,
            title=chart_title or "",
        )

        return {
            "success": True,
            "edit_type": "chart",
            "chart_type": chart_type,
            "path": validator.real_to_virtual(abs_path),
            **result,
        }

    else:
        raise ValueError(f"Unknown edit_type: {edit_type}")



