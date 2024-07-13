# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import re
import frappe

from erpnext_china.utils.lead_tools import get_doc_or_none
from erpnext.crm.doctype.lead.lead import Lead

class CustomLead(Lead):
	def create_contact(self):
		
		# TODO 根据phone WeChat qq等判断联系人是否已经存
		
		if not self.lead_name:
			self.set_full_name()
			self.set_lead_name()

		contact = frappe.new_doc("Contact")
		contact.update(
			{
				"first_name": self.first_name or self.lead_name,
				"last_name": self.last_name,
				"salutation": self.salutation,
				"gender": self.gender,
				"designation": self.job_title,
				"company_name": self.company_name,
				"custom_wechat":self.custom_wechat,
				"custom_qq":self.custom_qq
			}
		)

		if self.email_id:
			contact.append("email_ids", {"email_id": self.email_id, "is_primary": 1})

		if self.phone:
			contact.append("phone_nos", {"phone": self.phone, "is_primary_phone": 1})

		if self.mobile_no:
			contact.append("phone_nos", {"phone": self.mobile_no, "is_primary_mobile_no": 1})

		contact.insert(ignore_permissions=True)
		contact.reload()  # load changes by hooks on contact

		return contact

	def validate_single_phone(self):
		links = list(set([i for i in [self.phone, self.mobile_no, self.custom_wechat] + re.findall(r'\d+', self.custom_wechat or '')  if i]))
		or_filters = [
			{'phone': ['in', links]},
			{'mobile_no': ['in', links]},
			{'custom_wechat': ['in', links]}
		]
		filters = {"name": ['!=',self.name]}
		leads = frappe.get_all("Lead",filters=filters, or_filters=or_filters, fields=['name', 'lead_owner'])
		if len(leads) > 0:
			url = frappe.utils.get_url()
			message = []
			for lead in leads:
				lead_owner = ''
				if lead.lead_owner:
					user = frappe.get_doc("User", lead.lead_owner)
					if user: lead_owner = user.first_name
				message.append(f'{lead_owner}: <a href="{url}/app/lead/{lead.name}" target="_blank">{lead.name}</a>')
			message = ', '.join(message)
			frappe.throw(f"当前已经存在相同联系方式的线索: {frappe.bold(message)}", title='线索重复')

	def set_contact_info(self):
		if not any([self.phone, self.mobile_no, self.custom_wechat]):
			frappe.throw(f"联系方式必填")
		
		if self.phone:
			self.phone = str(self.phone).replace(' ','')
		if self.mobile_no:
			self.mobile_no = str(self.mobile_no).replace(' ','')
		if self.custom_wechat:
			self.custom_wechat = str(self.custom_wechat).replace(' ','')

	def validate(self):
		super().validate()
		self.set_contact_info()
		self.validate_single_phone()

	@property
	def custom_lead_owner_name(self):
		if self.lead_owner:
			lead_owner = get_doc_or_none('User', {
				'name': self.lead_owner
			})
			if lead_owner:
				return lead_owner.first_name
	
	def get_original_lead(self):
		original_leads = frappe.get_list('Original Leads', filters={'crm_lead': self.name}, order_by="creation")
		if len(original_leads) > 0:
			return frappe.get_doc('Original Leads', original_leads[0].name)
		return None
	
	@property
	def custom_original_lead_name(self):
		doc = self.get_original_lead()
		if doc:
			return doc.name

	@property
	def custom_site_url(self):
		doc = self.get_original_lead()
		if doc:
			return doc.site_url
	
	@property
	def custom_call_url(self):
		doc = self.get_original_lead()
		if doc:
			return doc.return_call_url

	@property
	def custom_lead_owner_leader_name(self):
		if self.lead_owner:
			employee = get_doc_or_none("Employee", {"user_id": self.lead_owner})
			if employee:
				employee_leader_name = employee.reports_to
				if employee_leader_name:
					employee_leader = frappe.get_doc("Employee", employee_leader_name)
					return employee_leader.user_id
	
	@property
	def custom_created_by(self):
		doc = frappe.get_doc('User', self.owner)
		return doc.first_name

	def before_save(self):
		if len(self.notes) > 0:
			notes = sorted(self.notes, key=lambda x: x.added_on, reverse=True)
			latest_note = notes[0]
			if latest_note.added_by == self.lead_owner:
				self.custom_latest_note_created_time = latest_note.added_on
				self.custom_latest_note = latest_note.note
		doc = get_doc_or_none('Lead', self.name)
		if doc:
			self.custom_last_lead_owner = doc.lead_owner
		else:
			self.custom_last_lead_owner = ''


@frappe.whitelist()
def get_lead(**kwargs):
	lead_name = kwargs.get('lead')
	if lead_name:
		lead = frappe.get_doc('Lead', lead_name)
		employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, fieldname="name")
		if lead and employee:
			lead.custom_lead_owner_employee = employee
			lead.lead_owner = frappe.session.user
			lead.save(ignore_permissions=True)


@frappe.whitelist()
def give_up_lead(**kwargs):
	lead_name = kwargs.get('lead')
	if lead_name:
		lead = frappe.get_doc('Lead', lead_name)
		if lead:
			lead.custom_lead_owner_employee = ''
			lead.lead_owner = ''
			lead.save(ignore_permissions=True)