from sqlalchemy.orm import Session

from app.db.models.master_data import Product, Supplier, SupplierDocument


class SuppliersRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_name_key(self, name_key: str) -> Supplier | None:
        return self.db.query(Supplier).filter(Supplier.name_key == name_key).first()

    def create(self, data: dict) -> Supplier:
        row = Supplier(**data)
        self.db.add(row)
        self.db.flush()
        return row

    def list_all(self) -> list[Supplier]:
        return self.db.query(Supplier).order_by(Supplier.name.asc(), Supplier.id.asc()).all()

    def get_by_id(self, supplier_id: int) -> Supplier | None:
        return self.db.query(Supplier).filter(Supplier.id == supplier_id).first()

    def list_products(self) -> list[Product]:
        return self.db.query(Product).order_by(Product.tjx_style.asc(), Product.id.asc()).all()

    def create_document(self, data: dict) -> SupplierDocument:
        row = SupplierDocument(**data)
        self.db.add(row)
        self.db.flush()
        return row

    def list_documents_by_supplier(self, supplier_id: int) -> list[SupplierDocument]:
        return (
            self.db.query(SupplierDocument)
            .filter(SupplierDocument.supplier_id == supplier_id)
            .order_by(SupplierDocument.uploaded_at.desc(), SupplierDocument.id.desc())
            .all()
        )

    def get_document_by_id(self, supplier_id: int, document_id: int) -> SupplierDocument | None:
        return (
            self.db.query(SupplierDocument)
            .filter(
                SupplierDocument.id == document_id,
                SupplierDocument.supplier_id == supplier_id,
            )
            .first()
        )

    def update_document_name(
        self,
        supplier_id: int,
        document_id: int,
        file_name: str,
    ) -> SupplierDocument | None:
        row = self.get_document_by_id(supplier_id=supplier_id, document_id=document_id)
        if row is None:
            return None
        row.file_name = file_name
        self.db.flush()
        return row

    def delete_document(self, supplier_id: int, document_id: int) -> SupplierDocument | None:
        row = self.get_document_by_id(supplier_id=supplier_id, document_id=document_id)
        if row is None:
            return None
        self.db.delete(row)
        self.db.flush()
        return row
