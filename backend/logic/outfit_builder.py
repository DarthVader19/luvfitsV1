from database.models import Product, SessionLocal

def build_outfit():
    session = SessionLocal()
    top = session.query(Product).filter(Product.category == "Tops").first()
    bottom = session.query(Product).filter(Product.category == "Bottoms").first()
    accessory = session.query(Product).filter(Product.category == "Accessories").first()
    shoe = session.query(Product).filter(Product.category == "Shoes").first()
    session.close()
    return {
        "top": top.__dict__ if top else None,
        "bottom": bottom.__dict__ if bottom else None,
        "accessory": accessory.__dict__ if accessory else None,
        "shoe": shoe.__dict__ if shoe else None
    }