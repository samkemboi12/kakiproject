import os
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, RawMaterial, MaterialMovement, Shift, ProductionRound, Roll, Product, FinishedMovement, Sale, Expense
RECIPES={'LINEAR':{'HD':25,'LLD':4.5,'LD':3},'SABIC':{'HD':25,'LLD':3,'LD':1.5,'MB':2}}; PIN=os.environ.get('KHAKI_PIN','2468')
def stock(mid): return round(sum(x.quantity_kg for x in MaterialMovement.query.filter_by(material_id=mid)),2)
def product_stock(pid): return sum(x.packets for x in FinishedMovement.query.filter_by(product_id=pid))
def money(v): return f'KES {v:,.0f}'
def net_roll_weight(round_): return sum(r.gross_kg-2 for r in round_.rolls)
def seed():
 if RawMaterial.query.first(): return
 mats=[RawMaterial(code='HD',name='High Density Polyethylene',unit_cost=190),RawMaterial(code='LLD',name='Linear Low Density',unit_cost=205),RawMaterial(code='LD',name='Low Density Polyethylene',unit_cost=215),RawMaterial(code='MB',name='Black Masterbatch',unit_cost=480)]; products=[Product(sku='LIN-BLK',name='Linear Black Packaging Paper',quality='LINEAR',price_per_packet=145),Product(sku='SAB-BLK',name='Sabic Premium Packaging Paper',quality='SABIC',price_per_packet=175)]; db.session.add_all(mats+products); db.session.flush(); today=date.today()
 for m,q in zip(mats,[2800,850,650,300]): db.session.add(MaterialMovement(material_id=m.id,movement_date=today-timedelta(days=14),movement_type='Receipt',quantity_kg=q,reference='GRN-2401'))
 for i in range(8):
  sd=today-timedelta(days=7-i); s=Shift(shift_date=sd,shift_type='Day' if i%2==0 else 'Night',operator=['James Mwangi','Amina Yusuf','Peter Otieno'][i%3],notes='Handover verified'); db.session.add(s); db.session.flush(); quality='LINEAR' if i%3 else 'SABIC'; recipe=RECIPES[quality]; inp=sum(recipe.values())*4; waste=round(inp*.028,1); r=ProductionRound(shift_id=s.id,quality=quality,input_kg=inp,waste_kg=waste,leftover_kg=0); db.session.add(r); db.session.flush()
  for mach in 'ABC': db.session.add(Roll(production_round_id=r.id,machine=mach,gross_kg=round((inp-waste)/3+2,1)))
  for code,amt in recipe.items(): db.session.add(MaterialMovement(material_id=next(x for x in mats if x.code==code).id,movement_date=sd,movement_type='Issued',quantity_kg=-amt*4,reference=f'PR-{r.id:03d}'))
 for p,prod,sold in [(products[0],2300,1300),(products[1],1800,900)]: db.session.add(FinishedMovement(product_id=p.id,movement_date=today-timedelta(days=5),movement_type='Packaged',packets=prod,reference='PACK-01')); db.session.add(FinishedMovement(product_id=p.id,movement_date=today-timedelta(days=1),movement_type='Dispatch',packets=-sold,reference='DSP-01')); db.session.add(Sale(sale_date=today-timedelta(days=1),customer='Metro Wholesale Ltd',product_id=p.id,packets=sold,amount=sold*p.price_per_packet,status='Dispatched'))
 db.session.add_all([Expense(expense_date=today-timedelta(days=3),category='Power',description='Plant electricity',amount=54000),Expense(expense_date=today-timedelta(days=2),category='Transport',description='Customer dispatches',amount=18500),Expense(expense_date=today,category='Maintenance',description='Machine B bearings',amount=12000)]); db.session.commit()
def create_app():
 app=Flask(__name__); app.config.update(SECRET_KEY=os.environ.get('KHAKI_SECRET_KEY','khaki-local-key'),SQLALCHEMY_DATABASE_URI='sqlite:///'+os.path.join(app.instance_path,'khaki_biz.sqlite3'),SQLALCHEMY_TRACK_MODIFICATIONS=False); os.makedirs(app.instance_path,exist_ok=True); db.init_app(app)
 with app.app_context(): db.create_all(); seed()
 app.jinja_env.globals.update(stock=stock,product_stock=product_stock,money=money,recipes=RECIPES,net_roll_weight=net_roll_weight)
 @app.before_request
 def protect():
  if request.endpoint not in ('login','static') and not session.get('logged_in'): return redirect(url_for('login'))
 @app.route('/login',methods=['GET','POST'])
 def login():
  if request.method=='POST':
   if request.form.get('pin')==PIN: session['logged_in']=True; return redirect(url_for('dashboard'))
   flash('Incorrect PIN. Please try again.','error')
  return render_template('login.html')
 @app.get('/logout')
 def logout(): session.clear(); return redirect(url_for('login'))
 @app.get('/')
 def dashboard():
  sales=sum(s.amount for s in Sale.query.all()); expenses=sum(e.amount for e in Expense.query.all()); produced=sum(r.input_kg-r.waste_kg-r.leftover_kg for r in ProductionRound.query.all()); return render_template('dashboard.html',sales=sales,expenses=expenses,profit=sales-expenses,produced=produced,rounds=ProductionRound.query.order_by(ProductionRound.id.desc()).limit(6).all(),materials=RawMaterial.query.all(),products=Product.query.all())
 @app.route('/raw-materials',methods=['GET','POST'])
 def raw_materials():
  if request.method=='POST':
   m=db.session.get(RawMaterial,int(request.form['material_id'])); qty=float(request.form['quantity']);
   if qty<=0: flash('Quantity must be positive.','error')
   else: db.session.add(MaterialMovement(material_id=m.id,movement_date=date.today(),movement_type='Receipt',quantity_kg=qty,reference=request.form.get('reference','GRN-MANUAL'))); db.session.commit(); flash('Raw material receipt posted.','success')
   return redirect(url_for('raw_materials'))
  return render_template('raw_materials.html',materials=RawMaterial.query.all(),moves=MaterialMovement.query.order_by(MaterialMovement.id.desc()).limit(12).all())
 @app.route('/production',methods=['GET','POST'])
 def production():
  if request.method=='POST':
   quality=request.form['quality']; batches=int(request.form['batches']); recipe=RECIPES[quality]; needed={c:q*batches for c,q in recipe.items()}; mats={m.code:m for m in RawMaterial.query.all()}
   if any(stock(mats[c].id)<q for c,q in needed.items()): flash('Insufficient raw-material stock for this recipe.','error'); return redirect(url_for('production'))
   s=Shift(shift_date=date.fromisoformat(request.form['shift_date']),shift_type=request.form['shift_type'],operator=request.form['operator'],notes=request.form.get('notes','')); db.session.add(s); db.session.flush(); total=sum(needed.values()); r=ProductionRound(shift_id=s.id,quality=quality,input_kg=total,waste_kg=float(request.form['waste']),leftover_kg=float(request.form['leftover'])); db.session.add(r); db.session.flush()
   for c,q in needed.items(): db.session.add(MaterialMovement(material_id=mats[c].id,movement_date=s.shift_date,movement_type='Issued',quantity_kg=-q,reference=f'PR-{r.id:03d}'))
   for mach in 'ABC':
    gross=float(request.form.get('machine_'+mach,0));
    if gross>0: db.session.add(Roll(production_round_id=r.id,machine=mach,gross_kg=gross))
   db.session.commit(); flash('Production round recorded and raw materials issued.','success'); return redirect(url_for('production'))
  return render_template('production.html',rounds=ProductionRound.query.order_by(ProductionRound.id.desc()).all(),today=date.today().isoformat())
 @app.route('/finished-goods',methods=['GET','POST'])
 def finished_goods():
  if request.method=='POST': db.session.add(FinishedMovement(product_id=int(request.form['product_id']),movement_date=date.today(),movement_type='Packaged',packets=int(request.form['packets']),reference='PACK-MANUAL')); db.session.commit(); flash('Finished packets added to stock.','success'); return redirect(url_for('finished_goods'))
  return render_template('finished_goods.html',products=Product.query.all(),moves=FinishedMovement.query.order_by(FinishedMovement.id.desc()).limit(12).all())
 @app.route('/sales',methods=['GET','POST'])
 def sales():
  if request.method=='POST':
   p=db.session.get(Product,int(request.form['product_id'])); packets=int(request.form['packets'])
   if packets>product_stock(p.id): flash('Not enough finished goods available.','error')
   else: db.session.add(Sale(sale_date=date.today(),customer=request.form['customer'],product_id=p.id,packets=packets,amount=packets*p.price_per_packet,status='Dispatched')); db.session.add(FinishedMovement(product_id=p.id,movement_date=date.today(),movement_type='Dispatch',packets=-packets,reference='DSP-MANUAL')); db.session.commit(); flash('Sale and dispatch posted.','success')
   return redirect(url_for('sales'))
  return render_template('sales.html',products=Product.query.all(),sales=Sale.query.order_by(Sale.id.desc()).all())
 @app.route('/expenses',methods=['GET','POST'])
 def expenses():
  if request.method=='POST': db.session.add(Expense(expense_date=date.today(),category=request.form['category'],description=request.form['description'],amount=float(request.form['amount']))); db.session.commit(); flash('Expense recorded.','success'); return redirect(url_for('expenses'))
  return render_template('expenses.html',expenses=Expense.query.order_by(Expense.id.desc()).all())
 @app.get('/reports')
 def reports(): return render_template('reports.html',rounds=ProductionRound.query.order_by(ProductionRound.id.desc()).all(),sales=Sale.query.order_by(Sale.id.desc()).all())
 return app
app=create_app()
if __name__=='__main__': app.run(debug=True,port=5001)
