from database.models import Product, SessionLocal
from logic.outfit_builder import build_outfit

def search_outfits(query):
    session = SessionLocal()
    products = session.query(Product).filter(Product.tags.contains(query)).all()
    session.close()

    if not products:
        return build_outfit()

    # Group by category
    cats = {}
    for p in products:
        cat = p.category
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(p)

    # Find most common color
    colors = [p.color for p in products if p.color]
    if colors:
        most_common_color = max(set(colors), key=colors.count)
        outfit = {}
        for cat in ["Tops", "Bottoms", "Accessories", "Shoes"]:
            if cat in cats:
                matching = [p for p in cats[cat] if p.color == most_common_color]
                if matching:
                    outfit[cat.lower()] = matching[0].__dict__
                else:
                    outfit[cat.lower()] = cats[cat][0].__dict__
            else:
                session = SessionLocal()
                fallback = session.query(Product).filter(Product.category == cat).first()
                outfit[cat.lower()] = fallback.__dict__ if fallback else None
                session.close()
    else:
        # Use most common tag
        all_tags = [tag.strip() for p in products for tag in p.tags.split(',')]
        if all_tags:
            most_common_tag = max(set(all_tags), key=all_tags.count)
            outfit = {}
            for cat in ["Tops", "Bottoms", "Accessories", "Shoes"]:
                if cat in cats:
                    matching = [p for p in cats[cat] if most_common_tag in p.tags]
                    if matching:
                        outfit[cat.lower()] = matching[0].__dict__
                    else:
                        outfit[cat.lower()] = cats[cat][0].__dict__
                else:
                    session = SessionLocal()
                    fallback = session.query(Product).filter(Product.category == cat).first()
                    outfit[cat.lower()] = fallback.__dict__ if fallback else None
                    session.close()
        else:
            outfit = {}
            for cat in ["Tops", "Bottoms", "Accessories", "Shoes"]:
                if cat in cats:
                    outfit[cat.lower()] = cats[cat][0].__dict__
                else:
                    session = SessionLocal()
                    fallback = session.query(Product).filter(Product.category == cat).first()
                    outfit[cat.lower()] = fallback.__dict__ if fallback else None
                    session.close()

    return outfit