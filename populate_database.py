from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Base, Category, Item
__author__ = 'Sai'
engine = create_engine('sqlite:///itemcatalog.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()


# Items for Football
category1 = Category(name="Football")

session.add(category1)
session.commit()

item1 = Item(title="Football", description="A black and white ball",
             category=category1, picture='football.jpg')

session.add(item1)
session.commit()


# Items for Cricket
category2 = Category(name="Cricket")

session.add(category2)
session.commit()

item1 = Item(title="Bat", description="A wooden bat to strike the ball with",
             category=category2, picture='cricket_bat.jpg')

session.add(item1)
session.commit()

item2 = Item(title="Ball", description="A red coloured ball made of cork",
             category=category2, picture='cricket_ball.jpg')

session.add(item2)
session.commit()

item3 = Item(title="Wicket", description="A wicket made out of wood",
             category=category2, picture='cricket_wicket.jpg')

session.add(item3)
session.commit()


print("added menu items!")
