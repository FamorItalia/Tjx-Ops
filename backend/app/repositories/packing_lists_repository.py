import re

from sqlalchemy.orm import Session, selectinload

from app.db.models.customer_orders import CustomerOrder
from app.db.models.master_data import DistributionCenter, Product, Supplier
from app.db.models.packing_lists import PackingList, PackingListLine
from app.db.models.purchase_orders import PurchaseOrder


class PackingListsRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def style_key(value: str | None) -> str | None:
        if not value:
            return None
        return re.sub(r"[^A-Z0-9]", "", value.upper()) or None

    def get_purchase_order(self, purchase_order_id: int) -> PurchaseOrder | None:
        return (
            self.db.query(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .filter(PurchaseOrder.id == purchase_order_id)
            .first()
        )

    def get_purchase_order_by_customer_order(self, customer_order_id: int) -> PurchaseOrder | None:
        return (
            self.db.query(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .filter(PurchaseOrder.customer_order_id == customer_order_id)
            .first()
        )

    def get_customer_order(self, customer_order_id: int) -> CustomerOrder | None:
        return (
            self.db.query(CustomerOrder)
            .options(selectinload(CustomerOrder.lines))
            .filter(CustomerOrder.id == customer_order_id)
            .first()
        )

    def get_supplier_by_name(self, name: str | None) -> Supplier | None:
        if not name:
            return None
        key = self.style_key(name)
        if not key:
            return None
        return self.db.query(Supplier).filter(Supplier.name_key == key).first()

    def get_distribution_centers(self, brand: str | None, codes: list[str]) -> dict[str, DistributionCenter]:
        if not brand or not codes:
            return {}
        rows = (
            self.db.query(DistributionCenter)
            .filter(
                DistributionCenter.brand == brand,
                DistributionCenter.dc_code.in_(codes),
            )
            .all()
        )
        return {x.dc_code: x for x in rows}

    def list_distribution_centers_by_brand(self, brand: str | None) -> list[DistributionCenter]:
        if not brand:
            return []
        return (
            self.db.query(DistributionCenter)
            .filter(DistributionCenter.brand == brand)
            .order_by(DistributionCenter.id.asc())
            .all()
        )

    def get_products_by_styles(self, styles: list[str]) -> dict[str, Product]:
        keys = [self.style_key(x) for x in styles]
        keys = [x for x in keys if x]
        if not keys:
            return {}
        rows = self.db.query(Product).filter(Product.tjx_style_key.in_(keys)).all()
        return {x.tjx_style_key: x for x in rows if x.tjx_style_key}

    def create_packing_list(self, data: dict, lines_data: list[dict]) -> PackingList:
        row = PackingList(**data)
        self.db.add(row)
        self.db.flush()
        for line in lines_data:
            self.db.add(PackingListLine(packing_list_id=row.id, **line))
        self.db.commit()
        self.db.refresh(row)
        return self.get_packing_list(row.id) or row

    def delete_by_purchase_order_id(self, purchase_order_id: int) -> None:
        rows = (
            self.db.query(PackingList)
            .filter(PackingList.purchase_order_id == purchase_order_id)
            .all()
        )
        for row in rows:
            self.db.delete(row)
        self.db.commit()

    def get_packing_list(self, packing_list_id: int) -> PackingList | None:
        return (
            self.db.query(PackingList)
            .options(selectinload(PackingList.lines))
            .filter(PackingList.id == packing_list_id)
            .first()
        )

    def list_by_purchase_order_id(self, purchase_order_id: int) -> list[PackingList]:
        return (
            self.db.query(PackingList)
            .options(selectinload(PackingList.lines))
            .filter(PackingList.purchase_order_id == purchase_order_id)
            .order_by(PackingList.dc_code.asc(), PackingList.id.asc())
            .all()
        )

    def update_packing_list_fields(self, packing_list_id: int, fields: dict) -> PackingList | None:
        row = self.db.query(PackingList).filter(PackingList.id == packing_list_id).first()
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        self.db.commit()
        self.db.refresh(row)
        return self.get_packing_list(packing_list_id)
