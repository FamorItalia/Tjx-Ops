from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.routes.auth import router as auth_router
from app.api.routes.brands import router as brands_router
from app.api.routes.email import router as email_router
from app.api.routes.distribution_centers import router as distribution_centers_router
from app.api.routes.files import router as files_router
from app.api.routes.health import router as health_router
from app.api.routes.orders import router as orders_router
from app.api.routes.packing_lists import router as packing_lists_router
from app.api.routes.parser import router as parser_router
from app.api.routes.products import router as products_router
from app.api.routes.purchase_orders import router as purchase_orders_router
from app.api.routes.suppliers import router as suppliers_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
protected = [Depends(get_current_user)]
api_router.include_router(files_router, dependencies=protected)
api_router.include_router(parser_router, dependencies=protected)
api_router.include_router(orders_router, dependencies=protected)
api_router.include_router(brands_router, dependencies=protected)
api_router.include_router(purchase_orders_router, dependencies=protected)
api_router.include_router(products_router, dependencies=protected)
api_router.include_router(distribution_centers_router, dependencies=protected)
api_router.include_router(suppliers_router, dependencies=protected)
api_router.include_router(email_router, dependencies=protected)
api_router.include_router(packing_lists_router, dependencies=protected)
