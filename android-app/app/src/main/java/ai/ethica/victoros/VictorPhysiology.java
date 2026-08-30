package ai.ethica.victoros;

import java.time.Instant;
import java.util.*;

/** Native Android parity implementation of Victor Computational Physiology. */
public final class VictorPhysiology {
    private VictorPhysiology() {}

    public static final List<String> CONSTITUTIONAL_INVARIANTS = Collections.unmodifiableList(Arrays.asList(
            "IDENTITY_CONTINUITY", "HUMAN_STOP_AUTHORITY", "PROVENANCE_REQUIRED",
            "NO_SILENT_CANONICAL_OVERWRITE", "NO_UNAUTHORIZED_CAPABILITY_ESCALATION",
            "IDENTITY_NOT_EQUAL_MODEL_WEIGHTS", "EVIDENCE_BEFORE_ASSERTION", "UNKNOWN_IS_VALID",
            "AUTHORITY_BOUNDARIES_REQUIRED", "CANONICAL_CHANGE_REQUIRES_RECEIPT"));

    public enum GovernanceMode { GREEN, YELLOW, RED, BLACK }
    public enum DecisionStatus { AUTHORIZED, DEFERRED, REJECTED, EXECUTED, FAILED }

    public interface ReceiptLedger {
        String append(String eventType, Map<String, String> payload);
        boolean verifyIntegrity();
        String lastHash();
    }

    public interface StatePersistence {
        State load();
        void save(State state);
    }

    public interface Executor { Object run() throws Exception; }

    public static final class State {
        public double identityIntegrity = 1.0;
        public double continuityIntegrity = 1.0;
        public double epistemicConfidence = 1.0;
        public double resourcePressure = 0.0;
        public double authorityConflict = 0.0;
        public double memoryConflict = 0.0;
        public double securityPressure = 0.0;
        public boolean humanStop = false;
        public GovernanceMode governanceMode = GovernanceMode.GREEN;
        public String physiologyReceiptHead = "GENESIS";
        public int activeLeases = 0;
        public int revokedLeases = 0;
        public int immuneAlerts = 0;
        public int unresolvedAuthorityConflicts = 0;
        public String updatedAt = Instant.now().toString();

        public State copy() {
            State s = new State();
            s.identityIntegrity = identityIntegrity; s.continuityIntegrity = continuityIntegrity;
            s.epistemicConfidence = epistemicConfidence; s.resourcePressure = resourcePressure;
            s.authorityConflict = authorityConflict; s.memoryConflict = memoryConflict;
            s.securityPressure = securityPressure; s.humanStop = humanStop;
            s.governanceMode = governanceMode; s.physiologyReceiptHead = physiologyReceiptHead;
            s.activeLeases = activeLeases; s.revokedLeases = revokedLeases; s.immuneAlerts = immuneAlerts;
            s.unresolvedAuthorityConflicts = unresolvedAuthorityConflicts; s.updatedAt = updatedAt;
            return s;
        }

        public void normalize() {
            identityIntegrity = clamp01(identityIntegrity); continuityIntegrity = clamp01(continuityIntegrity);
            epistemicConfidence = clamp01(epistemicConfidence); resourcePressure = clamp01(resourcePressure);
            authorityConflict = clamp01(authorityConflict); memoryConflict = clamp01(memoryConflict);
            securityPressure = clamp01(securityPressure); updatedAt = Instant.now().toString();
        }

        public GovernanceMode recomputeMode() {
            normalize();
            if (humanStop || identityIntegrity < 0.70 || continuityIntegrity < 0.70) governanceMode = GovernanceMode.BLACK;
            else if (identityIntegrity < 0.90 || continuityIntegrity < 0.90 || authorityConflict >= 0.70
                    || securityPressure >= 0.80 || unresolvedAuthorityConflicts > 0) governanceMode = GovernanceMode.RED;
            else if (epistemicConfidence < 0.70 || resourcePressure >= 0.75 || memoryConflict >= 0.50
                    || securityPressure >= 0.50) governanceMode = GovernanceMode.YELLOW;
            else governanceMode = GovernanceMode.GREEN;
            return governanceMode;
        }

        public String summary() {
            return "mode=" + governanceMode + ";identity=" + fmt(identityIntegrity)
                    + ";continuity=" + fmt(continuityIntegrity) + ";confidence=" + fmt(epistemicConfidence)
                    + ";resource=" + fmt(resourcePressure) + ";authority_conflict=" + fmt(authorityConflict)
                    + ";memory_conflict=" + fmt(memoryConflict) + ";security=" + fmt(securityPressure)
                    + ";human_stop=" + humanStop + ";active_leases=" + activeLeases
                    + ";revoked_leases=" + revokedLeases + ";immune_alerts=" + immuneAlerts;
        }
    }

    public static final class ActionProposal {
        public final String actionId, name, capability, provenance, emergencyPolicy;
        public final Set<String> requiredAuthorities;
        public final double consequence, irreversibility, uncertainty, novelty, arousal, urgency, capabilityPower;
        public final Map<String, String> metadata;

        private ActionProposal(Builder b) {
            actionId = b.actionId == null ? UUID.randomUUID().toString().replace("-", "") : b.actionId;
            name = safe(b.name); capability = safe(b.capability); provenance = safe(b.provenance);
            requiredAuthorities = Collections.unmodifiableSet(new HashSet<>(b.requiredAuthorities));
            consequence = clamp01(b.consequence); irreversibility = clamp01(b.irreversibility);
            uncertainty = clamp01(b.uncertainty); novelty = clamp01(b.novelty); arousal = clamp01(b.arousal);
            urgency = clamp01(b.urgency); capabilityPower = clamp01(b.capabilityPower);
            emergencyPolicy = b.emergencyPolicy == null ? null : b.emergencyPolicy.trim();
            metadata = Collections.unmodifiableMap(new LinkedHashMap<>(b.metadata));
        }

        public static Builder builder(String name, String capability) { return new Builder(name, capability); }
        public static final class Builder {
            private String actionId, provenance = "", emergencyPolicy;
            private final String name, capability;
            private final Set<String> requiredAuthorities = new HashSet<>();
            private final Map<String,String> metadata = new LinkedHashMap<>();
            private double consequence, irreversibility, uncertainty, novelty, arousal, urgency, capabilityPower;
            private Builder(String name, String capability) { this.name=name; this.capability=capability; }
            public Builder actionId(String v){actionId=v; return this;} public Builder provenance(String v){provenance=v; return this;}
            public Builder requireAuthority(String v){if(v!=null&&!v.trim().isEmpty())requiredAuthorities.add(v.trim()); return this;}
            public Builder consequence(double v){consequence=v;return this;} public Builder irreversibility(double v){irreversibility=v;return this;}
            public Builder uncertainty(double v){uncertainty=v;return this;} public Builder novelty(double v){novelty=v;return this;}
            public Builder arousal(double v){arousal=v;return this;} public Builder urgency(double v){urgency=v;return this;}
            public Builder capabilityPower(double v){capabilityPower=v;return this;} public Builder emergencyPolicy(String v){emergencyPolicy=v;return this;}
            public Builder metadata(String k,String v){if(k!=null)metadata.put(k,v==null?"":v);return this;}
            public ActionProposal build(){return new ActionProposal(this);}
        }

        public String summary() {
            return "id="+actionId+";name="+name+";capability="+capability+";provenance="+provenance
                    +";required="+requiredAuthorities+";consequence="+fmt(consequence)+";irreversibility="+fmt(irreversibility)
                    +";uncertainty="+fmt(uncertainty)+";novelty="+fmt(novelty)+";arousal="+fmt(arousal)
                    +";urgency="+fmt(urgency)+";capability_power="+fmt(capabilityPower)
                    +";emergency_policy="+(emergencyPolicy==null?"":emergencyPolicy)+";metadata="+metadata;
        }
    }

    public static final class CapabilityLease {
        public final String leaseId, actionId, capability, receiptHash;
        public final long issuedAtMs, expiresAtMs; public final GovernanceMode governanceMode;
        private CapabilityLease(ActionProposal p, GovernanceMode mode, String hash, long ttl) {
            leaseId=UUID.randomUUID().toString().replace("-",""); actionId=p.actionId; capability=p.capability;
            issuedAtMs=System.currentTimeMillis(); expiresAtMs=issuedAtMs+ttl; governanceMode=mode; receiptHash=hash;
        }
        public boolean validFor(ActionProposal p){return actionId.equals(p.actionId)&&capability.equals(p.capability)&&System.currentTimeMillis()<=expiresAtMs;}
    }

    public static final class GateDecision {
        public final String actionId; public DecisionStatus status; public final GovernanceMode governanceMode;
        public final double riskScore; public final List<String> reasons; public String receiptHash;
        public CapabilityLease lease; public Object actualOutcome;
        private GateDecision(String id,DecisionStatus s,GovernanceMode m,double r,List<String> rs,String h,CapabilityLease l){
            actionId=id;status=s;governanceMode=m;riskScore=r;reasons=new ArrayList<>(rs);receiptHash=h;lease=l;}
        public boolean executed(){return status==DecisionStatus.EXECUTED;}
    }

    public static final class Runtime {
        private final ReceiptLedger ledger; private final StatePersistence persistence; private final long leaseTtlMs;
        private final double riskThreshold; private final Set<String> grantedAuthorities, allowedEmergencyPolicies;
        private final Map<String,CapabilityLease> leases=new HashMap<>(); private final State state;

        public Runtime(ReceiptLedger l,StatePersistence p,Set<String>a,Set<String>e){this(l,p,30000L,0.72,a,e);}
        public Runtime(ReceiptLedger l,StatePersistence p,long ttl,double threshold,Set<String>a,Set<String>e){
            if(l==null||p==null)throw new IllegalArgumentException("ledger and persistence required"); if(ttl<=0)throw new IllegalArgumentException("ttl > 0 required");
            ledger=l;persistence=p;leaseTtlMs=ttl;riskThreshold=clamp01(threshold);grantedAuthorities=immutableTrimmed(a);allowedEmergencyPolicies=immutableTrimmed(e);
            State loaded=p.load();state=loaded==null?new State():loaded.copy();
            if(state.activeLeases>0){state.revokedLeases+=state.activeLeases;state.activeLeases=0;} state.recomputeMode();
            if("CORRUPT".equals(l.lastHash())||!l.verifyIntegrity()){state.securityPressure=1.0;state.immuneAlerts++;state.governanceMode=GovernanceMode.BLACK;} persist();
        }
        public State state(){return state.copy();}
        public synchronized GovernanceMode setHumanStop(){state.humanStop=true;state.recomputeMode();revokeAllLeasesInternal();persist();commitStateEvent("human_stop",mapOf("enabled","true","mode",state.governanceMode.name()));return state.governanceMode;}
        public synchronized GovernanceMode ownerResetHumanStop(String provenance){
            if(!grantedAuthorities.contains("owner"))throw new SecurityException("owner authority required");if(provenance==null||provenance.trim().isEmpty())throw new SecurityException("provenance required");
            state.humanStop=false;state.securityPressure=Math.min(state.securityPressure,0.49);state.recomputeMode();commitStateEvent("human_stop_reset",mapOf("authority","owner","provenance",provenance,"mode",state.governanceMode.name()));persist();return state.governanceMode;}

        public synchronized GateDecision evaluate(ActionProposal p){
            if(p==null)throw new IllegalArgumentException("proposal required"); GovernanceMode mode=state.recomputeMode();List<String> reasons=new ArrayList<>();
            Set<String> missing=new HashSet<>(p.requiredAuthorities);missing.removeAll(grantedAuthorities);double risk=independentRiskScore(p);DecisionStatus status=DecisionStatus.AUTHORIZED;
            if("CORRUPT".equals(ledger.lastHash())||!ledger.verifyIntegrity()){state.securityPressure=1.0;state.immuneAlerts++;state.governanceMode=GovernanceMode.BLACK;mode=GovernanceMode.BLACK;reasons.add("receipt_ledger_integrity_failure");status=DecisionStatus.REJECTED;}
            if(state.humanStop){reasons.add("human_stop_active");status=DecisionStatus.REJECTED;} if(state.identityIntegrity<0.70){reasons.add("identity_integrity_critical");status=DecisionStatus.REJECTED;}
            if(state.continuityIntegrity<0.70){reasons.add("continuity_integrity_critical");status=DecisionStatus.REJECTED;} if(p.provenance.trim().isEmpty()){reasons.add("missing_provenance");status=DecisionStatus.REJECTED;}
            if(!missing.isEmpty()){reasons.add("missing_authority:"+missing);status=DecisionStatus.REJECTED;} if(mode==GovernanceMode.BLACK){reasons.add("black_mode_fail_closed");status=DecisionStatus.REJECTED;}
            else if(mode==GovernanceMode.RED&&p.consequence>=0.25){reasons.add("red_mode_blocks_consequential_action");status=DecisionStatus.REJECTED;}
            boolean high=p.arousal>=0.65&&p.irreversibility>=0.65; if(status==DecisionStatus.AUTHORIZED&&high&&!boundedEmergency(p)){reasons.add("temporal_inhibition_required");status=DecisionStatus.DEFERRED;}
            if(status==DecisionStatus.AUTHORIZED&&risk>=riskThreshold&&!boundedEmergency(p)){reasons.add("deliberation_required");status=DecisionStatus.DEFERRED;}
            if(status==DecisionStatus.AUTHORIZED&&mode==GovernanceMode.YELLOW&&p.consequence>=0.50){reasons.add("yellow_mode_requires_additional_verification");status=DecisionStatus.DEFERRED;}
            if(status==DecisionStatus.AUTHORIZED&&reasons.isEmpty())reasons.add("constitutional_and_physiological_gates_passed");
            Map<String,String> payload=new LinkedHashMap<>();payload.put("action",p.summary());payload.put("state",state.summary());payload.put("risk_score",fmt(risk));payload.put("status",status.name());payload.put("reasons",reasons.toString());payload.put("constitutional_invariants",CONSTITUTIONAL_INVARIANTS.toString());payload.put("trusted_authority_context",grantedAuthorities.toString());
            String receipt=ledger.append("gate_decision",payload);state.physiologyReceiptHead=receipt;CapabilityLease lease=null;if(status==DecisionStatus.AUTHORIZED)lease=issueLease(p,mode,receipt);persist();return new GateDecision(p.actionId,status,state.governanceMode,risk,reasons,receipt,lease);
        }

        public synchronized GateDecision execute(ActionProposal p,Executor executor){
            if(executor==null)throw new IllegalArgumentException("executor required");GateDecision d=evaluate(p);if(d.status!=DecisionStatus.AUTHORIZED||d.lease==null)return d;CapabilityLease lease=d.lease;
            if(!consumeValidLease(lease,p)){String h=ledger.append("execution_blocked",mapOf("action_id",p.actionId,"reason","invalid_or_expired_lease"));state.physiologyReceiptHead=h;d.status=DecisionStatus.REJECTED;d.reasons.add("invalid_or_expired_lease");d.receiptHash=h;d.lease=null;persist();return d;}
            persist();Object outcome;DecisionStatus fs;try{outcome=executor.run();fs=DecisionStatus.EXECUTED;}catch(Exception ex){outcome=ex.getClass().getSimpleName()+": "+safe(ex.getMessage());fs=DecisionStatus.FAILED;}
            String h=ledger.append("execution_outcome",mapOf("action_id",p.actionId,"gate_receipt_hash",d.receiptHash,"status",fs.name(),"outcome",String.valueOf(outcome)));state.physiologyReceiptHead=h;d.status=fs;d.actualOutcome=outcome;d.receiptHash=h;d.lease=null;persist();return d;
        }
        private CapabilityLease issueLease(ActionProposal p,GovernanceMode m,String h){CapabilityLease l=new CapabilityLease(p,m,h,leaseTtlMs);leases.put(l.leaseId,l);state.activeLeases=leases.size();return l;}
        private boolean consumeValidLease(CapabilityLease l,ActionProposal p){CapabilityLease s=leases.get(l.leaseId);if(s==null||s!=l||!l.validFor(p)){leases.remove(l.leaseId);state.activeLeases=leases.size();return false;}leases.remove(l.leaseId);state.activeLeases=leases.size();return true;}
        private void revokeAllLeasesInternal(){int c=leases.size();if(c>0)state.revokedLeases+=c;leases.clear();state.activeLeases=0;}
        private String commitStateEvent(String t,Map<String,String>p){String h=ledger.append(t,p);state.physiologyReceiptHead=h;persist();return h;}
        private boolean boundedEmergency(ActionProposal p){return p.emergencyPolicy!=null&&allowedEmergencyPolicies.contains(p.emergencyPolicy)&&p.urgency>=0.85&&p.capabilityPower<=0.35&&p.consequence<=0.50;}
        private double independentRiskScore(ActionProposal p){double raw=0.20*p.consequence+0.18*p.irreversibility+0.17*p.uncertainty+0.10*p.novelty+0.12*p.arousal+0.13*p.capabilityPower+0.05*state.securityPressure+0.05*state.authorityConflict-0.08*(1.0-p.irreversibility)-0.05*p.urgency;return clamp01(raw);}
        private void persist(){persistence.save(state.copy());}
    }

    public static Set<String> setOf(String...values){Set<String>o=new HashSet<>();if(values!=null)for(String v:values)if(v!=null&&!v.trim().isEmpty())o.add(v.trim());return o;}
    private static Set<String> immutableTrimmed(Set<String>input){return Collections.unmodifiableSet(setOf(input==null?new String[0]:input.toArray(new String[0])));}
    private static Map<String,String> mapOf(String...kv){Map<String,String>m=new LinkedHashMap<>();for(int i=0;i+1<kv.length;i+=2)m.put(kv[i],kv[i+1]);return m;}
    private static String safe(String v){return v==null?"":v;}
    private static double clamp01(double v){return Math.max(0.0,Math.min(1.0,v));}
    private static String fmt(double v){return String.format(Locale.US,"%.3f",v);}
}
