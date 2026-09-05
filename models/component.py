from dataclasses import dataclass, fields, field
from datetime import datetime
from typing import Optional

def _now_str() -> str:
    """生成当前时间字符串，格式：YYYY-MM-DD HH:MM:SS"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class Component:
    """元件数据模型，对应数据库 components 表"""
    purpose: str
    generic_desc: str
    model: str
    package: str = ""
    pin_count: int = 0
    key_params: str = ""
    pin_notes: str = ""
    lcsc_id: str = ""
    buy_link: str = ""
    current_price: float = 0.0
    supplier: str = ""
    status: str = "未验证"
    created_at: str = field(default_factory=_now_str)
    updated_at: str = field(default_factory=_now_str)
    price_updated_at: str = field(default_factory=_now_str)
    id: Optional[int] = None

    def to_dict(self) -> dict:
        """将对象转换为字典，包含所有字段"""
        return {
            "id": self.id,
            "purpose": self.purpose,
            "generic_desc": self.generic_desc,
            "model": self.model,
            "package": self.package,
            "pin_count": self.pin_count,
            "key_params": self.key_params,
            "pin_notes": self.pin_notes,
            "lcsc_id": self.lcsc_id,
            "buy_link": self.buy_link,
            "current_price": self.current_price,
            "supplier": self.supplier,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "price_updated_at": self.price_updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Component':
        """
        从字典创建对象，忽略不存在的字段。
        这样可以兼容数据库查询返回的不同列集合。
        """
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)