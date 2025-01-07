from os import environ
from .models import WalkingBus, db
from sqlalchemy.exc import IntegrityError


def init_walking_buses():
    buses_env = environ.get('WALKING_BUSES', '').strip()
    
    if not buses_env:
        return False
    
    # Store configured bus IDs for later use
    bus_definitions = buses_env.split(',')
    configured_bus_ids = []
    is_multi_bus = len(bus_definitions) > 1
    
    with db.session.no_autoflush:
        for bus_def in bus_definitions:
            try:
                bus_id, name, password = bus_def.split(':')
                bus_id = int(bus_id)
                configured_bus_ids.append(bus_id)
                
                existing_bus = WalkingBus.query.get(bus_id)
                if existing_bus:
                    existing_bus.name = name
                    existing_bus.password = password
                else:
                    new_bus = WalkingBus(
                        id=bus_id,
                        name=name, 
                        password=password
                    )
                    db.session.add(new_bus)
                    
            except (ValueError, TypeError) as e:
                print(f"Invalid bus definition: {bus_def} - {str(e)}")
                continue
        
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("Database error during bus initialization")
        
        # Store configured bus IDs in app config for use in routes
        from flask import current_app
        current_app.config['CONFIGURED_BUS_IDS'] = configured_bus_ids
        
        return is_multi_bus

