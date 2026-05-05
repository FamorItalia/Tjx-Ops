from sqlalchemy.orm import Session

from app.db.models.master_data import DistributionCenter


class DistributionCentersRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_brand_code(self, brand: str, dc_code: str) -> DistributionCenter | None:
        return (
            self.db.query(DistributionCenter)
            .filter(DistributionCenter.brand == brand, DistributionCenter.dc_code == dc_code)
            .first()
        )

    def create(self, data: dict) -> DistributionCenter:
        row = DistributionCenter(**data)
        self.db.add(row)
        self.db.flush()
        return row

    def list_all(self) -> list[DistributionCenter]:
        return (
            self.db.query(DistributionCenter)
            .order_by(DistributionCenter.brand.asc(), DistributionCenter.dc_code.asc())
            .all()
        )

    def get_by_id(self, dc_id: int) -> DistributionCenter | None:
        return self.db.query(DistributionCenter).filter(DistributionCenter.id == dc_id).first()

