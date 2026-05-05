from sqlalchemy.orm import Session

from app.db.models.master_data import Product, ProductDocument


class ProductsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_style_key(self, style_key: str) -> Product | None:
        return self.db.query(Product).filter(Product.tjx_style_key == style_key).first()

    def create(self, data: dict) -> Product:
        product = Product(**data)
        self.db.add(product)
        self.db.flush()
        return product

    def list_all(self) -> list[Product]:
        return self.db.query(Product).order_by(Product.tjx_style.asc(), Product.id.asc()).all()

    def get_by_id(self, product_id: int) -> Product | None:
        return self.db.query(Product).filter(Product.id == product_id).first()

    def create_document(self, data: dict) -> ProductDocument:
        row = ProductDocument(**data)
        self.db.add(row)
        self.db.flush()
        return row

    def list_documents_by_product(self, product_id: int) -> list[ProductDocument]:
        return (
            self.db.query(ProductDocument)
            .filter(ProductDocument.product_id == product_id)
            .order_by(ProductDocument.uploaded_at.desc(), ProductDocument.id.desc())
            .all()
        )

    def get_document_by_id(self, product_id: int, document_id: int) -> ProductDocument | None:
        return (
            self.db.query(ProductDocument)
            .filter(
                ProductDocument.id == document_id,
                ProductDocument.product_id == product_id,
            )
            .first()
        )

    def delete_document(self, product_id: int, document_id: int) -> ProductDocument | None:
        row = self.get_document_by_id(product_id=product_id, document_id=document_id)
        if row is None:
            return None
        self.db.delete(row)
        self.db.flush()
        return row
